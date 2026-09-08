"""
技能基类（Base Skill）。

技能是可复用的能力单元，被智能体调用以完成特定任务。

与 Tool 的区别：
  - Tool 是单个函数调用（如 search_knowledge）
  - Skill 是多步骤的能力组合（如 "分诊" = 检索 + 科室匹配 + 建议生成）

与 Agent 的区别：
  - Agent 有独立的推理循环和状态
  - Skill 被 Agent 调用，无独立状态，是 Agent 的能力插件
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseSkill(ABC):
    """技能抽象基类。"""

    name: str = "base_skill"
    description: str = ""
    required_tools: list[str] = []

    @abstractmethod
    def execute(self, state: dict, **kwargs) -> dict:
        """执行技能，返回结构化结果。

        Args:
            state: 共享状态（包含 role, user_id, kb_id 等）
            **kwargs: 技能特定参数

        Returns:
            dict: 技能执行结果（结构因技能而异）
        """

    @abstractmethod
    def is_applicable(self, question: str, state: dict) -> bool:
        """判断该技能是否适用于当前问题。"""

    def validate(self) -> bool:
        """验证技能所需的工具是否都已注册。"""
        from backend.agent import tools as toolmod
        for tool_name in self.required_tools:
            if not toolmod.get_tool(tool_name):
                return False
        return True
