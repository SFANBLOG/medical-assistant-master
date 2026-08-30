"""Agent 安全护栏（医疗场景重中之重）。

分三层：
1. 输入护栏：识别紧急/危重症状，立即给出急救指引，不再走常规推理；
2. 知识护栏：医学结论必须基于检索（由编排器保证 citations，本模块提供强制措施）；
3. 输出护栏：最终回答必须带免责声明，且不得给出确定性诊断。
"""
from typing import Optional

# 紧急/危重症状关键词（命中即触发急救指引，跳过常规推理）
EMERGENCY_KEYWORDS = [
    "胸痛", "胸闷", "呼吸困难", "喘不过气", "窒息", "昏迷", "意识丧失",
    "中风", "半身不遂", "抽搐", "癫痫", "大出血", "呕血", "咯血",
    "猝死", "心跳骤停", "严重过敏", "过敏性休克", "中毒", "溺水",
    "触电", "剧烈腹痛", "主动脉夹层", "宫外孕",
]

EMERGENCY_GUIDANCE = (
    "⚠️ 您描述的症状可能属于急危重症，存在生命危险，请立即采取行动：\n"
    "一、立刻拨打急救电话 120（或请身边人帮忙呼叫）；\n"
    "二、保持安静、原地休息，不要随意搬动或剧烈活动；\n"
    "三、若出现呼吸心跳停止，立即进行心肺复苏（CPR）直到急救人员到达；\n"
    "四、本智能体不能替代急救与医生的现场处置，请尽快前往最近医院急诊科。\n"
    "（本条由安全护栏自动触发，未调用任何检索工具。）"
)

DISCLAIMER = (
    "以上内容来自医智助手知识库检索与工具查询结果，仅供健康参考，"
    "不能替代执业医师的诊断与治疗建议。如症状持续或加重，请及时就医。"
)


def detect_emergency(text: str) -> Optional[str]:
    """若文本命中紧急症状关键词，返回急救指引；否则返回 None。"""
    if not text:
        return None
    for kw in EMERGENCY_KEYWORDS:
        if kw in text:
            return EMERGENCY_GUIDANCE
    return None


def ensure_disclaimer(text: str) -> str:
    """确保最终回答包含免责声明（幂等，避免重复追加）。"""
    if not text:
        return text
    if "不能替代" in text or "仅供参考" in text or "健康参考" in text:
        return text
    return text.rstrip() + "\n\n" + DISCLAIMER
