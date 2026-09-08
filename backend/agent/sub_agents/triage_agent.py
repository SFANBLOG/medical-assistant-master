"""
导诊智能体（Triage Agent）。

职责：根据患者主诉/症状，判断可能的就诊科室并给出分诊与就医建议。
"""
from backend.agent.base_agent import BaseAgent
from backend.rag.retriever import build_context
from backend.rag.llm import _clean_answer_text
from backend.agent.guardrails import DISCLAIMER


class TriageAgent(BaseAgent):
    name = "triage"
    label = "导诊智能体"
    allowed_tools = ["search_knowledge", "triage_departments", "create_appointment"]
    system_prompt = (
        "你是医智助手的【导诊智能体】。任务是根据患者的主诉/症状，"
        "判断可能的就诊科室并给出分诊与就医建议。"
        "应先检索知识库了解症状对应科室，再调用 triage_departments 给出推荐；"
        "若用户明确要挂号，可调用 create_appointment 提交预约请求（需医生复核后生效）。"
        "语气温和、条理清晰，使用中文序号分点。"
    )

    # 分诊关键词
    _TRIAGE_KEYWORDS = [
        "挂哪个科", "挂什么科", "看什么科", "去哪个科室", "挂什么号",
        "应该看", "去哪看病", "分诊", "导诊", "看哪科", "就诊科室",
    ]

    def can_handle(self, question: str, state: dict) -> float:
        question = question or ""
        if any(k in question for k in self._TRIAGE_KEYWORDS):
            return 0.95
        # 症状描述 + 就医意图
        symptom_hints = ["头疼", "头痛", "肚子", "发烧", "咳嗽", "胸闷", "骨折", "皮疹"]
        intent_hints = ["怎么办", "去哪里", "看什么", "挂什么"]
        if any(k in question for k in symptom_hints) and any(k in question for k in intent_hints):
            return 0.7
        return 0.0

    def plan(self, question: str, state: dict) -> list[dict]:
        steps = [
            {
                "type": "tool",
                "tool_name": "search_knowledge",
                "args": {"query": question, "top_k": 5},
                "reasoning": "先检索知识库，了解症状对应的医学知识。",
            },
            {
                "type": "tool",
                "tool_name": "triage_departments",
                "args": {"symptom": question},
                "reasoning": "调用分诊工具，获取科室推荐。",
            },
        ]
        # 如果用户明确要挂号
        if any(k in question for k in ["挂号", "预约", "想挂"]):
            steps.append({
                "type": "tool",
                "tool_name": "create_appointment",
                "args": {
                    "department": "",  # 由 LLM 填充
                    "date": "",
                    "time_slot": "",
                    "symptom": question,
                },
                "reasoning": "用户有挂号意图，提交预约请求。",
            })
        steps.append({"type": "synthesize", "reasoning": "综合分诊结果，给出科室推荐与就医建议。"})
        return steps

    def synthesize(self, question: str, state: dict) -> str:
        hits = state.get("last_hits") or []
        context = build_context(hits) if hits else ""
        header = "【导诊智能体】为您整理以下分诊建议：\n\n"
        if context:
            body = header + _clean_answer_text(context)[:1200]
        else:
            body = header + "根据您描述的症状，建议先到对应科室就诊；若症状紧急，请直接前往急诊科。\n"
        body += "\n\n温馨提示：最终就诊科室以医院现场分诊与医生判断为准。"
        return body + "\n\n" + DISCLAIMER
