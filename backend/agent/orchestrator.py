"""
ReAct 编排器（Agent 推理核心）。

对外暴露 run_agent() 生成器，逐步产出统一事件：
  - {"type":"thought",     "content": ...}   思考过程
  - {"type":"tool_call",   "name":..., "args":...}  调用了哪个工具
  - {"type":"observation", "content": ...}   工具返回（观察）
  - {"type":"citations",   "citations": [...]}  最终回答的引用来源
  - {"type":"message",     "content": ...}   最终回答（流式增量）
  - {"type":"done"}                             结束
  - {"type":"error",       "content": ...}   出错

两条执行路径：
  - 在线：OpenAI 兼容接口的函数调用（Think→Act→Observe 循环）
  - 离线：无 API key 或网络不可达时，用规则式 Agent（必检索知识库，含患者名则补查住院）
"""
from typing import Generator, Optional

import requests

from backend import config
from backend.agent import tools as toolmod
from backend.agent import guardrails, roles, memory
from backend.rag.retriever import build_context
from backend.rag.llm import _clean_answer_text
from backend.utils.db import fetchall


SYSTEM_PROMPT = (
    "你是「医智助手」的智能体（Medical Agent），具备规划与工具调用能力。"
    "你可以通过调用工具来获取信息，再综合给出回答。\n"
    "可用工具：search_knowledge（检索医学知识库）、reverse_geocode（经纬度→城市）、"
    "get_weather（获取天气）、query_hospitalizations（查询住院信息）、query_appointments（查询预约）、"
    "triage_departments（推荐就诊科室）、query_patient_records（查询病历）、"
    "create_appointment（提交预约请求，需医生复核后生效）。\n"
    "工作准则：\n"
    "1. 任何医学结论都必须先调用 search_knowledge 检索知识库，禁止凭空编造；\n"
    "2. 涉及患者/住院/预约等业务数据时，调用对应查询工具；\n"
    "3. 先在内心规划步骤，再一步步调用工具，最后综合成最终回答；\n"
    "4. 回答专业、温和、通俗易懂，使用中文序号（一、二、三）分点；\n"
    "5. 不得给出确定性诊断，仅作健康参考，并提示以医生诊断为准；\n"
    "6. 凡涉及预约/挂号等写操作，必须调用 create_appointment 提交复核，不得擅自直接建单；\n"
    "7. 输出不要使用 Markdown 符号（禁止 ** # - * 等）。"
)


def run_agent(
    question: str,
    role: str,
    user_id: int,
    kb_id: Optional[int] = None,
    history: Optional[list] = None,
    conv_id: Optional[str] = None,
) -> Generator[dict, None, None]:
    """运行 Agent，产出事件流。

    演进（见《Agent项目要点.md》）：
    - 输入护栏：紧急/危重症状直接拦截，给急救指引；
    - 角色路由（Supervisor）：按意图与身份选最合适的智能体；
    - 长期记忆：注入当前用户的病史/预约背景；
    - conv_id：关联会话，便于写操作（如预约请求）留痕溯源。
    """
    state = {"role": role, "user_id": user_id, "kb_id": kb_id, "last_hits": [], "conversation_id": conv_id}

    # 1) 输入护栏：紧急症状优先拦截，跳过常规推理
    emergency = guardrails.detect_emergency(question)
    if emergency:
        yield {"type": "meta", "role": "guardrail", "role_label": "安全护栏"}
        yield {"type": "thought", "content": "检测到紧急/危重症状，触发安全护栏，直接给出急救指引。"}
        yield from _emit_final(emergency, state)
        return

    # 2) 角色路由（Supervisor）
    role_key = roles.classify_role(question, role)
    role_info = roles.get_role(role_key)
    state["agent_role"] = role_key
    yield {"type": "meta", "role": role_key, "role_label": role_info["label"]}

    # 3) 长期记忆注入
    memory_ctx = memory.get_user_context(state)
    if memory_ctx:
        state["memory"] = memory_ctx

    # 在线优先；任何异常都降级到离线，保证全链路可用。
    if config.OPENAI_API_KEY and config.OPENAI_API_KEY not in ("", "sk-xxx"):
        try:
            yield from _run_online(question, state, history, role_key, memory_ctx)
            return
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "content": f"在线编排失败，已降级为离线模式：{e}"}

    yield from _run_offline(question, state, role_key, memory_ctx)


# ---------------------------------------------------------------------------
# 在线：OpenAI 函数调用循环
# ---------------------------------------------------------------------------

def _run_online(question: str, state: dict, history, role_key: str, memory_ctx: str) -> Generator[dict, None, None]:
    url = f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    # 角色专属系统提示 + 长期记忆注入；工具按角色白名单过滤
    role_info = roles.get_role(role_key)
    system = SYSTEM_PROMPT + "\n\n" + role_info["system_prompt"]
    if memory_ctx:
        system += f"\n\n用户长期记忆：{memory_ctx}"
    tool_schemas = roles.allowed_tool_schemas(toolmod.get_tool_schemas(), role_key)

    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": question})

    max_steps = 6
    for _ in range(max_steps):
        payload = {
            "model": config.OPENAI_CHAT_MODEL,
            "messages": messages,
            "tools": tool_schemas,
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 1024,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=25)
        if resp.status_code != 200:
            raise RuntimeError(f"API 返回 {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        msg = data["choices"][0]["message"]

        # 无工具调用 → 这就是最终回答
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            answer = msg.get("content") or ""
            yield from _emit_final(answer, state)
            return

        # 把带 tool_calls 的 assistant 消息加入上下文
        messages.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = __import__("json").loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            args = _inject_context(name, args, state)
            tool = toolmod.get_tool(name)

            # 工具执行出错不应打断整个推理循环：转成观察信息反馈给模型
            try:
                observation = tool.run(state, **args) if tool else f"未知工具：{name}"
            except Exception as e:  # noqa: BLE001
                observation = f"工具 {name} 执行出错：{e}"

            if msg.get("content"):
                yield {"type": "thought", "content": msg["content"]}
            yield {"type": "tool_call", "name": name, "args": args}
            yield {"type": "observation", "content": observation[:1500]}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "name": name,
                "content": observation,
            })

    yield {"type": "error", "content": "已达到最大推理步数，未能给出最终回答。"}


def _inject_context(name: str, args: dict, state: dict) -> dict:
    """为需要用户上下文的工具补齐参数。

    注意：role/user_id/kb_id 已存在于 state，工具函数从 state 中读取，
    不应作为工具入参传入（否则会触发意外的关键字参数错误）。
    """
    return args


# ---------------------------------------------------------------------------
# 离线：规则式 Agent（不依赖大模型 API）
# ---------------------------------------------------------------------------

def _run_offline(question: str, state: dict, role_key: str, memory_ctx: str) -> Generator[dict, None, None]:
    role_info = roles.get_role(role_key)
    yield {"type": "thought", "content": f"已路由至【{role_info['label']}】。先检索医学知识库获取权威资料。"}
    obs = toolmod.run_tool(state, "search_knowledge", query=question, top_k=5)
    yield {"type": "tool_call", "name": "search_knowledge", "args": {"query": question, "top_k": 5}}
    yield {"type": "observation", "content": obs[:1500]}

    # 角色专属工具协作
    if role_key in ("doctor", "nurse"):
        obs2 = toolmod.run_tool(state, "query_patient_records", keyword="")
        yield {"type": "tool_call", "name": "query_patient_records", "args": {"keyword": ""}}
        yield {"type": "observation", "content": obs2[:1500]}
    elif role_key == "triage":
        obs3 = toolmod.run_tool(state, "triage_departments", symptom=question)
        yield {"type": "tool_call", "name": "triage_departments", "args": {"symptom": question}}
        yield {"type": "observation", "content": obs3[:1500]}

    yield {"type": "thought", "content": "基于检索与查询结果，整理结构化回答。"}
    hits = state.get("last_hits") or []
    context = build_context(hits) if hits else ""
    answer = _synthesize(question, context, role_key, memory_ctx)
    yield from _emit_final(answer, state)


def _synthesize(question: str, context: str, role_key: str = "knowledge", memory_ctx: str = "") -> str:
    """离线合成最终回答（抽取式，不调用大模型）。"""
    role_label = roles.get_role(role_key)["label"]
    header = (
        f"【{role_label}】为您整理以下信息：\n\n"
        if role_key != "knowledge"
        else "根据知识库检索结果，为您整理以下信息：\n\n"
    )
    if context:
        body = header + _clean_answer_text(context)[:1500]
    else:
        body = (
            "抱歉，知识库中未检索到与您问题相关的内容。您可以尝试："
            "一，换一种方式描述问题；二，检查对应知识库是否已上传文档；"
            "三，联系医生上传更多相关资料。"
        )
    if memory_ctx:
        body += f"\n\n（已结合您的长期记忆：{memory_ctx}）"
    return body + "\n\n" + guardrails.DISCLAIMER


# ---------------------------------------------------------------------------
# 公共：事件产出
# ---------------------------------------------------------------------------

def _build_citations(state: dict) -> list:
    hits = state.get("last_hits") or []
    out = []
    for h in hits:
        out.append({
            "doc_id": h["doc_id"],
            "chunk_index": h.get("chunk_index", 0),
            "source_text": _clean_answer_text(h["text"])[:200],
            "title": h.get("filename", ""),
            "similarity": h["similarity"],
        })
    return out


def _emit_final(answer: str, state: dict) -> Generator[dict, None, None]:
    cites = _build_citations(state)
    if cites:
        yield {"type": "citations", "citations": cites}
    answer = guardrails.ensure_disclaimer(answer)
    yield from _stream_text(answer)


def _stream_text(text: str) -> Generator[dict, None, None]:
    text = _clean_answer_text(text)
    for i in range(0, len(text), 3):
        yield {"type": "message", "content": text[i:i + 3]}
    yield {"type": "done"}
