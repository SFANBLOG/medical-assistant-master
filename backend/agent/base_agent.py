"""
子智能体基类（Base Agent）。

所有子智能体（导诊/医生/护士/知识/排班/随访）继承此基类，
获得统一的 ReAct 生命周期：plan → act → observe → synthesize。

与现有代码的关系：
  - allowed_tools 替代 roles.py 中 ROLES[key]["allowed_tools"]
  - system_prompt 替代 roles.py 中 ROLES[key]["system_prompt"]
  - run() 生成器模式与现有 SSE 管线（service.py）完全兼容
  - 工具调用复用 tools.py 中的 Tool 类和 run_tool() 函数
"""
from abc import ABC, abstractmethod
from typing import Generator, Optional

from backend import config
from backend.agent import tools as toolmod
from backend.rag.retriever import build_context
from backend.rag.llm import _clean_answer_text
from backend.agent.guardrails import ensure_disclaimer, DISCLAIMER


class BaseAgent(ABC):
    """子智能体抽象基类。"""

    name: str = "base"
    label: str = "基础智能体"
    allowed_tools: list[str] = []
    system_prompt: str = ""

    # ------------------------------------------------------------------
    # 抽象方法：子类必须实现
    # ------------------------------------------------------------------

    @abstractmethod
    def can_handle(self, question: str, state: dict) -> float:
        """返回 0.0~1.0 的置信度，表示该智能体处理此问题的适合程度。

        Supervisor 据此做路由决策辅助。离线模式用此值做关键词匹配，
        在线模式可结合 LLM 分类结果。
        """

    @abstractmethod
    def plan(self, question: str, state: dict) -> list[dict]:
        """生成执行计划。

        每步为 dict，包含：
          - {"type": "tool", "tool_name": "...", "args": {...}, "reasoning": "..."}
          - {"type": "delegate", "delegate_to": "...", "question": "...", "reasoning": "..."}
          - {"type": "synthesize", "reasoning": "..."}  # 最终合成
        """

    # ------------------------------------------------------------------
    # 可选覆盖方法
    # ------------------------------------------------------------------

    def observe(self, result: str, step: dict, state: dict) -> None:
        """整合观察结果到内部状态。子类可覆盖以更新推理链。"""
        pass

    def synthesize(self, question: str, state: dict) -> str:
        """合成最终回答。子类可覆盖以定制输出格式。"""
        hits = state.get("last_hits") or []
        context = build_context(hits) if hits else ""
        if context:
            body = _clean_answer_text(context)[:1500]
        else:
            body = (
                "抱歉，知识库中未检索到与您问题相关的内容。您可以尝试："
                "一，换一种方式描述问题；二，检查对应知识库是否已上传文档；"
                "三，联系医生上传更多相关资料。"
            )
        return body + "\n\n" + DISCLAIMER

    # ------------------------------------------------------------------
    # 公共方法：标准 ReAct 循环
    # ------------------------------------------------------------------

    def run(
        self,
        question: str,
        state: dict,
        history: Optional[list] = None,
        memory_ctx: str = "",
    ) -> Generator[dict, None, None]:
        """运行智能体，产出事件流（与现有 SSE 管线兼容）。

        两条路径：
          - 在线：OpenAI 函数调用循环（Think→Act→Observe）
          - 离线：按 plan() 执行工具调用，规则合成回答
        """
        if config.OPENAI_API_KEY and config.OPENAI_API_KEY not in ("", "sk-xxx"):
            try:
                yield from self._run_online(question, state, history, memory_ctx)
                return
            except Exception as e:  # noqa: BLE001
                yield {"type": "error", "content": f"在线编排失败，降级为离线模式：{e}"}

        yield from self._run_offline(question, state, memory_ctx)

    # ------------------------------------------------------------------
    # 在线：OpenAI 函数调用循环
    # ------------------------------------------------------------------

    def _run_online(
        self, question: str, state: dict, history: Optional[list], memory_ctx: str
    ) -> Generator[dict, None, None]:
        """在线模式：OpenAI 兼容接口的函数调用循环。"""
        import requests
        import json

        url = f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        # 构建系统提示
        system = self._build_system_prompt(memory_ctx)
        tool_schemas = self._get_tool_schemas()

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
                yield from self._emit_final(answer, state)
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

    # ------------------------------------------------------------------
    # 离线：规则式执行
    # ------------------------------------------------------------------

    def _run_offline(
        self, question: str, state: dict, memory_ctx: str
    ) -> Generator[dict, None, None]:
        """离线模式：按 plan() 逐步执行工具调用，规则合成回答。"""
        yield {"type": "thought", "content": f"已路由至【{self.label}】。正在规划执行步骤。"}

        steps = self.plan(question, state)
        for step in steps:
            step_type = step.get("type", "")

            if step_type == "tool":
                tool_name = step["tool_name"]
                args = step.get("args", {})
                reasoning = step.get("reasoning", "")

                if reasoning:
                    yield {"type": "thought", "content": reasoning}

                obs = toolmod.run_tool(state, tool_name, **args)
                yield {"type": "tool_call", "name": tool_name, "args": args}
                yield {"type": "observation", "content": obs[:1500]}
                self.observe(obs, step, state)

            elif step_type == "delegate":
                # 委派给其他智能体（由 Supervisor 在更高层处理）
                yield {
                    "type": "thought",
                    "content": f"需要委派给【{step.get('delegate_to', '')}】处理。",
                }

        yield {"type": "thought", "content": "基于执行结果，整理结构化回答。"}
        answer = self.synthesize(question, state)
        if memory_ctx:
            answer += f"\n\n（已结合您的长期记忆：{memory_ctx}）"
        yield from self._emit_final(answer, state)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _build_system_prompt(self, memory_ctx: str = "") -> str:
        """构建完整系统提示（基础提示 + 角色提示 + 记忆注入）。"""
        base = (
            "你是「医智助手」的智能体（Medical Agent），具备规划与工具调用能力。"
            "你可以通过调用工具来获取信息，再综合给出回答。\n"
            "工作准则：\n"
            "1. 任何医学结论都必须先调用 search_knowledge 检索知识库，禁止凭空编造；\n"
            "2. 涉及患者/住院/预约等业务数据时，调用对应查询工具；\n"
            "3. 先在内心规划步骤，再一步步调用工具，最后综合成最终回答；\n"
            "4. 回答专业、温和、通俗易懂，使用中文序号（一、二、三）分点；\n"
            "5. 不得给出确定性诊断，仅作健康参考，并提示以医生诊断为准；\n"
            "6. 凡涉及预约/挂号等写操作，必须调用 create_appointment 提交复核，不得擅自直接建单；\n"
            "7. 输出不要使用 Markdown 符号（禁止 ** # - * 等）。"
        )
        parts = [base, self.system_prompt]
        if memory_ctx:
            parts.append(f"\n\n用户长期记忆：{memory_ctx}")
        return "\n\n".join(parts)

    def _get_tool_schemas(self) -> list[dict]:
        """获取本智能体可用工具的 OpenAI schema。"""
        all_schemas = toolmod.get_tool_schemas()
        allowed = set(self.allowed_tools)
        return [s for s in all_schemas if s.get("function", {}).get("name") in allowed]

    def _emit_final(self, answer: str, state: dict) -> Generator[dict, None, None]:
        """产出最终回答事件（引用 + 流式文本）。"""
        cites = self._build_citations(state)
        if cites:
            yield {"type": "citations", "citations": cites}
        answer = ensure_disclaimer(answer)
        yield from self._stream_text(answer)

    def _build_citations(self, state: dict) -> list:
        """从 state 中的 last_hits 构建引用列表。"""
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

    @staticmethod
    def _stream_text(text: str) -> Generator[dict, None, None]:
        """将文本拆为小块流式产出。"""
        text = _clean_answer_text(text)
        for i in range(0, len(text), 3):
            yield {"type": "message", "content": text[i:i + 3]}
        yield {"type": "done"}
