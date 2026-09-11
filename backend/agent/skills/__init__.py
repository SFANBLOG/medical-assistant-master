"""
技能系统（Skills）。

技能是可复用的能力单元，被智能体调用以完成特定任务。
与 Tool 的区别：Tool 是单函数调用，Skill 是多步骤的能力组合。
与 Agent 的区别：Agent 有独立推理循环，Skill 无独立状态。
"""
from backend.agent.skills.appointment_skill import AppointmentSkill
from backend.agent.skills.base_skill import BaseSkill
from backend.agent.skills.health_education import HealthEducationSkill
from backend.agent.skills.medical_qa import MedicalQASkill
from backend.agent.skills.patient_records_skill import PatientRecordsSkill
from backend.agent.skills.triage_skill import TriageSkill

# 技能注册表
SKILL_REGISTRY: dict[str, type[BaseSkill]] = {
    "medical_qa": MedicalQASkill,
    "triage": TriageSkill,
    "appointment": AppointmentSkill,
    "patient_records": PatientRecordsSkill,
    "health_education": HealthEducationSkill,
}


def get_skill(skill_key: str) -> BaseSkill:
    """按 key 获取技能实例。"""
    cls = SKILL_REGISTRY.get(skill_key)
    if cls:
        return cls()
    raise ValueError(f"未知技能：{skill_key}")


def get_all_skills() -> list[BaseSkill]:
    """获取所有技能实例。"""
    return [cls() for cls in SKILL_REGISTRY.values()]


def find_applicable_skills(question: str, state: dict) -> list[BaseSkill]:
    """找出适用于当前问题的技能列表。"""
    result = []
    for cls in SKILL_REGISTRY.values():
        skill = cls()
        if skill.is_applicable(question, state):
            result.append(skill)
    return result
