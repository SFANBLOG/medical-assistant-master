"""
子智能体注册表。

所有子智能体在此注册，Supervisor 通过 AGENT_REGISTRY 获取实例。
"""
from backend.agent.sub_agents.triage_agent import TriageAgent
from backend.agent.sub_agents.doctor_agent import DoctorAgent
from backend.agent.sub_agents.nurse_agent import NurseAgent
from backend.agent.sub_agents.knowledge_agent import KnowledgeAgent
from backend.agent.sub_agents.schedule_agent import ScheduleAgent
from backend.agent.sub_agents.followup_agent import FollowUpAgent

# 子智能体注册表：key → 类
AGENT_REGISTRY: dict[str, type] = {
    "triage": TriageAgent,
    "doctor": DoctorAgent,
    "nurse": NurseAgent,
    "knowledge": KnowledgeAgent,
    "schedule": ScheduleAgent,
    "followup": FollowUpAgent,
}


def get_agent(agent_key: str):
    """按 key 获取子智能体实例，找不到则返回知识智能体（兜底）。"""
    cls = AGENT_REGISTRY.get(agent_key, AGENT_REGISTRY["knowledge"])
    return cls()


def get_all_agents() -> list:
    """获取所有子智能体实例（Supervisor 用于遍历分类）。"""
    return [cls() for cls in AGENT_REGISTRY.values()]


def get_agent_labels() -> dict[str, str]:
    """返回所有智能体的 key→中文展示名映射。"""
    return {k: cls.label for k, cls in AGENT_REGISTRY.items()}
