"""
病历查询技能（Patient Records Skill）。

查询患者病历/住院记录。
"""
from backend.agent.skills.base_skill import BaseSkill
from backend.agent import tools as toolmod


class PatientRecordsSkill(BaseSkill):
    name = "patient_records"
    description = "查询患者病历汇总（住院记录），支持按关键词检索。"
    required_tools = ["query_patient_records"]

    def execute(self, state: dict, keyword: str = "") -> dict:
        """执行病历查询。

        Returns:
            dict: {
                "records": str,          # 病历文本
                "has_records": bool,     # 是否有记录
                "keyword": str,          # 查询关键词
            }
        """
        result = toolmod.run_tool(state, "query_patient_records", keyword=keyword)
        has_records = "未查询到" not in result and "病历汇总" in result

        return {
            "records": result,
            "has_records": has_records,
            "keyword": keyword,
        }

    def is_applicable(self, question: str, state: dict) -> bool:
        record_kw = ["病历", "病史", "住院记录", "检查记录", "患者档案"]
        # 医护角色查询病历时适用
        user_role = state.get("role", "public")
        if user_role in ("doctor", "nurse", "admin") and any(k in question for k in record_kw):
            return True
        return False
