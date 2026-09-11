"""
医生智能体（Doctor Agent）。

职责：结合病历/检索给诊断参考与用药建议（强制 HITL）。
"""
from backend.agent.base_agent import BaseAgent
from backend.agent.guardrails import DISCLAIMER
from backend.rag.llm import _clean_answer_text
from backend.rag.retriever import build_context


class DoctorAgent(BaseAgent):
    name = "doctor"
    label = "医生智能体"
    allowed_tools = [
        "search_knowledge", "query_patient_records",
        "query_hospitalizations", "query_appointments", "create_appointment",
    ]
    system_prompt = (
        "你是医智助手的【医生智能体】。可结合患者病历、住院与预约信息以及知识库检索，"
        "给出诊断思路、检查与用药的参考建议。"
        "务必先检索知识库、必要时查询患者档案；不得给出确定性诊断，"
        "所有用药/处置建议须提示『以接诊医生为准』并建议线下复诊。"
        "如需为患者预约，可调用 create_appointment 提交预约请求（需医生复核后生效）。"
    )

    _DOCTOR_KEYWORDS = [
        "吃什么药", "用什么药", "怎么治", "如何治疗", "诊断", "是什么病",
        "是不是", "严重吗", "用药", "治疗方案", "检查", "处方",
    ]
    _PATIENT_KEYWORDS = ["患者", "住院", "病历", "预约", "查房", "医嘱"]

    def can_handle(self, question: str, state: dict) -> float:
        question = question or ""
        user_role = state.get("role", "public")
        # 医护身份 + 涉及患者关键词
        if user_role in ("doctor", "nurse", "admin") and any(
            k in question for k in self._PATIENT_KEYWORDS
        ):
            return 0.95 if user_role == "doctor" else 0.6
        # 诊断/用药类问题
        if any(k in question for k in self._DOCTOR_KEYWORDS):
            return 0.8
        return 0.0

    def plan(self, question: str, state: dict) -> list[dict]:
        steps = []
        # 先查患者档案（如果是医护角色查询）
        if state.get("role") in ("doctor", "nurse", "admin"):
            steps.append({
                "type": "tool",
                "tool_name": "query_patient_records",
                "args": {"keyword": ""},
                "reasoning": "查询当前用户的患者档案，了解病史背景。",
            })
        # 检索医学知识
        steps.append({
            "type": "tool",
            "tool_name": "search_knowledge",
            "args": {"query": question, "top_k": 5},
            "reasoning": "检索知识库获取权威医学资料。",
        })
        # 必要时查住院信息
        if any(k in question for k in ["住院", "在院", "出院", "病房"]):
            steps.append({
                "type": "tool",
                "tool_name": "query_hospitalizations",
                "args": {"keyword": question[:20]},
                "reasoning": "问题涉及住院信息，查询住院记录。",
            })
        steps.append({"type": "synthesize", "reasoning": "综合病历与检索结果，给出诊断参考。"})
        return steps

    def synthesize(self, question: str, state: dict) -> str:
        hits = state.get("last_hits") or []
        context = build_context(hits) if hits else ""
        header = "【医生智能体】为您整理以下诊疗参考：\n\n"
        if context:
            body = header + _clean_answer_text(context)[:1200]
        else:
            body = header + "抱歉，知识库中未检索到与您问题相关的内容。建议携带相关检查资料到对应科室就诊。\n"
        body += "\n\n以上建议仅供参考，具体诊断与治疗方案请以接诊医生为准。建议线下复诊。"
        return body + "\n\n" + DISCLAIMER
