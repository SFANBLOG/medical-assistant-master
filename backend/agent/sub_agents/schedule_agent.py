"""
排班预约智能体（Schedule Agent）。

职责：排班查询、预约管理、时段可用性查询。
"""
from backend.agent.base_agent import BaseAgent
from backend.agent.guardrails import DISCLAIMER
from backend.rag.llm import _clean_answer_text
from backend.rag.retriever import build_context


class ScheduleAgent(BaseAgent):
    name = "schedule"
    label = "排班预约智能体"
    allowed_tools = ["query_appointments", "create_appointment", "search_knowledge", "query_schedules"]
    system_prompt = (
        "你是医智助手的【排班预约智能体】。负责排班查询、预约管理与时段可用性查询。"
        "先查询现有排班与预约信息，再根据用户需求推荐可用时段。"
        "如需提交预约请求，调用 create_appointment（需医生复核后生效）。"
        "语气清晰、准确，日期与时间信息务必准确。"
    )

    _SCHEDULE_KEYWORDS = [
        "排班", "预约", "挂号", "什么时候有号", "有号吗", "出诊",
        "门诊时间", "值班", "什么时候上班", "就诊时间", "可预约",
    ]

    def can_handle(self, question: str, state: dict) -> float:
        question = question or ""
        if any(k in question for k in self._SCHEDULE_KEYWORDS):
            return 0.9
        return 0.0

    def plan(self, question: str, state: dict) -> list[dict]:
        steps = [
            {
                "type": "tool",
                "tool_name": "query_schedules",
                "args": {"department": "", "date": ""},
                "reasoning": "查询排班信息，获取可用时段。",
            },
            {
                "type": "tool",
                "tool_name": "query_appointments",
                "args": {"keyword": ""},
                "reasoning": "查询现有预约信息。",
            },
        ]
        # 如果用户明确要预约
        if any(k in question for k in ["预约", "挂号", "帮我约"]):
            steps.append({
                "type": "tool",
                "tool_name": "search_knowledge",
                "args": {"query": question, "top_k": 3},
                "reasoning": "检索相关知识辅助预约建议。",
            })
        steps.append({"type": "synthesize", "reasoning": "综合排班与预约信息，给出建议。"})
        return steps

    def synthesize(self, question: str, state: dict) -> str:
        hits = state.get("last_hits") or []
        context = build_context(hits) if hits else ""
        header = "【排班预约智能体】为您整理以下信息：\n\n"
        body = header
        if context:
            body += _clean_answer_text(context)[:800] + "\n\n"
        body += "请根据以上排班信息选择合适的时段进行预约。如需提交预约请求，请告诉我科室、日期和时段。"
        return body + "\n\n" + DISCLAIMER
