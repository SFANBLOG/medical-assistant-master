"""
随访智能体（FollowUp Agent）。

职责：复诊随访、慢病管理、术后跟踪、健康管理提醒。
"""
from backend.agent.base_agent import BaseAgent
from backend.agent.guardrails import DISCLAIMER
from backend.rag.llm import _clean_answer_text
from backend.rag.retriever import build_context


class FollowUpAgent(BaseAgent):
    name = "followup"
    label = "随访智能体"
    allowed_tools = ["search_knowledge", "query_patient_records", "query_appointments"]
    system_prompt = (
        "你是医智助手的【随访智能体】。负责复诊随访、慢病管理、术后跟踪与健康提醒。"
        "先查询患者病史与近期预约，再检索随访指南，给出个性化随访建议。"
        "语气温和、关切，注重提醒与引导。"
    )

    _FOLLOWUP_KEYWORDS = [
        "复诊", "复查", "随访", "术后", "慢病", "定期", "跟踪",
        "健康管理", "出院后", "恢复情况", "后续治疗", "多久复查",
    ]

    def can_handle(self, question: str, state: dict) -> float:
        question = question or ""
        if any(k in question for k in self._FOLLOWUP_KEYWORDS):
            return 0.85
        return 0.0

    def plan(self, question: str, state: dict) -> list[dict]:
        steps = [
            {
                "type": "tool",
                "tool_name": "query_patient_records",
                "args": {"keyword": ""},
                "reasoning": "查询患者病史，了解随访背景。",
            },
            {
                "type": "tool",
                "tool_name": "search_knowledge",
                "args": {"query": question, "top_k": 5},
                "reasoning": "检索随访指南与健康管理知识。",
            },
            {
                "type": "tool",
                "tool_name": "query_appointments",
                "args": {"keyword": ""},
                "reasoning": "查询近期预约，判断是否需要安排复诊。",
            },
        ]
        steps.append({"type": "synthesize", "reasoning": "综合病史与随访指南，给出个性化随访建议。"})
        return steps

    def synthesize(self, question: str, state: dict) -> str:
        hits = state.get("last_hits") or []
        context = build_context(hits) if hits else ""
        header = "【随访智能体】为您整理以下随访建议：\n\n"
        if context:
            body = header + _clean_answer_text(context)[:1200]
        else:
            body = header + "根据您的情况，建议定期复诊，注意观察身体变化，如有异常及时就医。\n"
        body += "\n\n请遵医嘱按时复诊，如出现新症状或症状加重，请及时联系您的主治医生。"
        return body + "\n\n" + DISCLAIMER
