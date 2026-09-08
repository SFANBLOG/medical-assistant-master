"""
分诊技能（Triage Skill）。

症状→科室分诊推荐。
"""
from backend.agent.skills.base_skill import BaseSkill
from backend.agent import tools as toolmod


class TriageSkill(BaseSkill):
    name = "triage"
    description = "根据症状推荐就诊科室，用于导诊分流。"
    required_tools = ["search_knowledge", "triage_departments"]

    _TRIAGE_KEYWORDS = [
        "挂哪个科", "挂什么科", "看什么科", "去哪个科室", "挂什么号",
        "应该看", "去哪看病", "分诊", "导诊", "看哪科", "就诊科室",
    ]

    def execute(self, state: dict, symptom: str = "") -> dict:
        """执行分诊推荐。

        Returns:
            dict: {
                "departments": str,      # 科室推荐文本
                "knowledge": str,        # 知识库检索上下文
                "urgency": str,          # 紧急程度：normal/urgent/emergency
            }
        """
        # 调用分诊工具
        triage_result = toolmod.run_tool(state, "triage_departments", symptom=symptom)

        # 检索知识库补充
        toolmod.run_tool(state, "search_knowledge", query=symptom, top_k=3)

        # 判断紧急程度
        urgency = "normal"
        emergency_kw = ["剧烈", "突然", "严重", "持续加重", "无法忍受"]
        if any(k in symptom for k in emergency_kw):
            urgency = "urgent"

        return {
            "departments": triage_result,
            "urgency": urgency,
            "symptom": symptom,
        }

    def is_applicable(self, question: str, state: dict) -> bool:
        return any(k in question for k in self._TRIAGE_KEYWORDS)
