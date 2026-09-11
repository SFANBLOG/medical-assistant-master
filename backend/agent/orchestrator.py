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

架构升级（v2）：
  - Supervisor 智能路由：LLM 意图分类 + can_handle() 置信度路由
  - 子智能体体系：6 个独立子智能体（导诊/医生/护士/知识/排班/随访）
  - 技能系统：可复用的能力单元（medical_qa/triage/appointment/...）
  - 增强记忆：会话级工作记忆 + 长期用户画像

降级策略（v1）：
  - 设置 AGENT_MODE=v1 可回退到原有单体编排器
"""
from typing import Generator, Optional

from backend import config
from backend.agent import guardrails, memory
from backend.rag.llm import _clean_answer_text


def run_agent(
    question: str,
    role: str,
    user_id: int,
    kb_id: Optional[int] = None,
    history: Optional[list] = None,
    conv_id: Optional[str] = None,
) -> Generator[dict, None, None]:
    """运行 Agent，产出事件流。

    根据 AGENT_MODE 配置选择架构：
      - v2（默认）：Supervisor + 子智能体 + 技能系统
      - v1：原有单体编排器（降级兜底）
    """
    state = {"role": role, "user_id": user_id, "kb_id": kb_id, "last_hits": [], "conversation_id": conv_id}

    # 1) 输入护栏：紧急症状优先拦截，跳过常规推理
    emergency = guardrails.detect_emergency(question)
    if emergency:
        yield {"type": "meta", "role": "guardrail", "role_label": "安全护栏"}
        yield {"type": "thought", "content": "检测到紧急/危重症状，触发安全护栏，直接给出急救指引。"}
        yield from _emit_final(emergency, state)
        return

    # 2) 长期记忆注入
    memory_ctx = memory.get_enhanced_user_context(state) if config.AGENT_MODE == "v2" else memory.get_user_context(state)
    if memory_ctx:
        state["memory"] = memory_ctx

    # 3) 根据 AGENT_MODE 选择架构
    if config.AGENT_MODE == "v2":
        try:
            yield from _run_v2(question, state, history, memory_ctx)
            return
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "content": f"v2 架构异常，降级为 v1：{e}"}

    # v1 降级路径（原有单体编排器）
    yield from _run_v1(question, state, history, memory_ctx)


# ---------------------------------------------------------------------------
# v2：Supervisor + 子智能体
# ---------------------------------------------------------------------------

def _run_v2(
    question: str, state: dict, history: Optional[list], memory_ctx: str
) -> Generator[dict, None, None]:
    """v2 架构：Supervisor 智能路由 + 子智能体执行。"""
    from backend.agent.supervisor import Supervisor

    supervisor = Supervisor()
    yield from supervisor.route(question, state, history, memory_ctx)


# ---------------------------------------------------------------------------
# v1：原有单体编排器（降级兜底）
# ---------------------------------------------------------------------------

def _run_v1(
    question: str, state: dict, history: Optional[list], memory_ctx: str
) -> Generator[dict, None, None]:
    """v1 架构：原有单体编排器（关键字路由 + 在线/离线双路径）。"""
    from backend.agent import roles

    role_key = roles.classify_role(question, state.get("role", "public"))
    role_info = roles.get_role(role_key)
    state["agent_role"] = role_key
    yield {"type": "meta", "role": role_key, "role_label": role_info["label"]}

    if config.OPENAI_API_KEY and config.OPENAI_API_KEY not in ("", "sk-xxx"):
        try:
            yield from _run_online_v1(question, state, history, role_key, memory_ctx)
            return
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "content": f"在线编排失败，已降级为离线模式：{e}"}

    yield from _run_offline_v1(question, state, role_key, memory_ctx)



def _run_online_v1(question, state, history, role_key, memory_ctx):
    """v1 在线模式（原有逻辑）。"""
    import json
    import requests
    from backend.agent import roles
    from backend.agent import tools as toolmod

    url = f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    role_info = roles.get_role(role_key)
    system = (
        "你是「医智助手」的智能体（Medical Agent），具备规划与工具调用能力。\n"
        "可用工具：search_knowledge、reverse_geocode、get_weather、"
        "query_hospitalizations、query_appointments、triage_departments、"
        "query_patient_records、create_appointment、query_schedules。\n"
        "工作准则：先检索知识库，再综合回答；不得凭空编造；"
        "写操作需提交复核；输出不使用 Markdown 符号。"
        "\n\n" + role_info["system_prompt"]
    )
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

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            answer = msg.get("content") or ""
            yield from _emit_final(answer, state)
            return

        messages.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            tool = toolmod.get_tool(name)
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


def _run_offline_v1(question, state, role_key, memory_ctx):
    """v1 离线模式（原有逻辑）。"""
    from backend.agent import roles
    from backend.agent import tools as toolmod
    from backend.rag.retriever import build_context

    role_info = roles.get_role(role_key)
    yield {"type": "thought", "content": f"已路由至【{role_info['label']}】。先检索医学知识库获取权威资料。"}
    obs = toolmod.run_tool(state, "search_knowledge", query=question, top_k=5)
    yield {"type": "tool_call", "name": "search_knowledge", "args": {"query": question, "top_k": 5}}
    yield {"type": "observation", "content": obs[:1500]}

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
    answer = _synthesize_v1(question, context, role_key, memory_ctx)
    yield from _emit_final(answer, state)


def _synthesize_v1(question, context, role_key="knowledge", memory_ctx=""):
    """v1 离线合成。"""
    from backend.agent import roles
    from backend.rag.llm import _clean_answer_text

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
