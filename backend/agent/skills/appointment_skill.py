"""
预约工作流技能（Appointment Skill）。

预约挂号工作流，包含 HITL 审计与防重复提交。
"""
from backend.agent.skills.base_skill import BaseSkill
from backend.agent import tools as toolmod


class AppointmentSkill(BaseSkill):
    name = "appointment"
    description = "预约挂号工作流（含 HITL 复核与防重复提交）。"
    required_tools = ["query_appointments", "create_appointment"]

    def execute(
        self,
        state: dict,
        department: str = "",
        date: str = "",
        time_slot: str = "",
        symptom: str = "",
        **kwargs,
    ) -> dict:
        """执行预约工作流。

        Returns:
            dict: {
                "success": bool,         # 是否成功提交
                "request_id": str,       # 预约请求 ID
                "status": str,           # 状态：pending_review / failed
                "message": str,          # 结果消息
            }
        """
        # 参数验证
        if not department or not date or not time_slot:
            return {
                "success": False,
                "request_id": "",
                "status": "failed",
                "message": "预约失败：科室、日期、时段均为必填项。",
            }

        # 提交预约请求（自动走 HITL 复核流程）
        result = toolmod.run_tool(
            state, "create_appointment",
            department=department,
            date=date,
            time_slot=time_slot,
            symptom=symptom,
            **kwargs,
        )

        # 判断结果
        success = "已生成预约请求" in result or "已提交" in result
        return {
            "success": success,
            "request_id": self._extract_request_id(result),
            "status": "pending_review" if success else "failed",
            "message": result,
        }

    def is_applicable(self, question: str, state: dict) -> bool:
        appointment_kw = ["预约", "挂号", "帮我约", "想挂号", "挂号预约"]
        return any(k in question for k in appointment_kw)

    @staticmethod
    def _extract_request_id(text: str) -> str:
        """从结果文本中提取预约请求 ID。"""
        import re
        match = re.search(r"#(\d+)", text)
        return match.group(1) if match else ""
