"""
护士智能体（Nurse Agent）。

职责：护理要点、用药指导、康复与健康教育。
"""
from backend.agent.base_agent import BaseAgent
from backend.agent.guardrails import DISCLAIMER
from backend.rag.llm import _clean_answer_text
from backend.rag.retriever import build_context


class NurseAgent(BaseAgent):
    name = "nurse"
    label = "护士智能体"
    allowed_tools = ["search_knowledge", "query_patient_records", "create_appointment"]
    system_prompt = (
        "你是医智助手的【护士智能体】。负责护理要点、用药指导、康复与健康教育。"
        "应先检索知识库获取权威护理/康复知识，必要时查询患者档案。"
        "语气耐心、细致，多用分点说明。"
        "如需为患者预约复诊，可调用 create_appointment 提交预约请求（需医生复核后生效）。"
    )

    _NURSE_KEYWORDS = [
        "怎么护理", "如何护理", "注意事项", "康复", "术后", "饮食注意",
        "用药指导", "护理要点", "换药", "复查", "健康宣教", "日常注意",
    ]

    def can_handle(self, question: str, state: dict) -> float:
        question = question or ""
        user_role = state.get("role", "public")
        if user_role == "nurse" and any(
                k in question for k in ["患者", "护理", "医嘱", "查房"]
        ):
            return 0.9
        if any(k in question for k in self._NURSE_KEYWORDS):
            return 0.8
        return 0.0

    def plan(self, question: str, state: dict) -> list[dict]:
        steps = [
            {
                "type": "tool",
                "tool_name": "search_knowledge",
                "args": {"query": question, "top_k": 5},
                "reasoning": "先检索知识库获取权威护理/康复知识。",
            },
        ]
        # 医护角色时查患者档案
        if state.get("role") in ("doctor", "nurse", "admin"):
            steps.append({
                "type": "tool",
                "tool_name": "query_patient_records",
                "args": {"keyword": ""},
                "reasoning": "查询患者档案，了解护理背景。",
            })
        steps.append({"type": "synthesize", "reasoning": "综合护理知识，给出护理指导。"})
        return steps

    def synthesize(self, question: str, state: dict) -> str:
        hits = state.get("last_hits") or []
        context = build_context(hits) if hits else ""
        header = "【护士智能体】为您整理以下护理指导：\n\n"
        if context:
            body = header + _clean_answer_text(context)[:1200]
        else:
            body = header + "根据您描述的情况，建议注意日常护理与观察，如有异常及时就医。\n"
        body += "\n\n如有不适或症状加重，请及时联系医护人员。"
        return body + "\n\n" + DISCLAIMER
