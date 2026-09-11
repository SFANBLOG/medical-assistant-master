"""多角色智能体（Supervisor–Worker）轻量实现。

Supervisor 根据问题意图与用户身份，把任务派给最合适的工作智能体：
- triage    导诊智能体：识别症状，推荐就诊科室
- doctor    医生智能体：结合病历/检索给诊断与用药参考（强制 HITL）
- nurse     护士智能体：护理、用药指导、康复宣教
- knowledge 知识智能体：纯 RAG 问答

每个角色有专属系统提示与「可用工具白名单」，在线模式下据此过滤函数调用，
离线模式下据此决定调用哪些工具与回答口吻。
"""

ROLES = {
    "triage": {
        "label": "导诊智能体",
        "allowed_tools": ["search_knowledge", "triage_departments", "create_appointment"],
        "system_prompt": (
            "你是医智助手的【导诊智能体】。任务是根据患者的主诉/症状，"
            "判断可能的就诊科室并给出分诊与就医建议。"
            "应先检索知识库了解症状对应科室，再调用 triage_departments 给出推荐；"
            "若用户明确要挂号，可调用 create_appointment 提交预约请求（需医生复核后生效）。"
            "语气温和、条理清晰，使用中文序号分点。"
        ),
    },
    "doctor": {
        "label": "医生智能体",
        "allowed_tools": [
            "search_knowledge", "query_patient_records",
            "query_hospitalizations", "query_appointments", "create_appointment",
        ],
        "system_prompt": (
            "你是医智助手的【医生智能体】。可结合患者病历、住院与预约信息以及知识库检索，"
            "给出诊断思路、检查与用药的参考建议。"
            "务必先检索知识库、必要时查询患者档案；不得给出确定性诊断，"
            "所有用药/处置建议须提示『以接诊医生为准』并建议线下复诊。"
            "如需为患者预约，可调用 create_appointment 提交预约请求（需医生复核后生效）。"
        ),
    },
    "nurse": {
        "label": "护士智能体",
        "allowed_tools": ["search_knowledge", "query_patient_records", "create_appointment"],
        "system_prompt": (
            "你是医智助手的【护士智能体】。负责护理要点、用药指导、康复与健康教育。"
            "应先检索知识库获取权威护理/康复知识，必要时查询患者档案。"
            "语气耐心、细致，多用分点说明。"
            "如需为患者预约复诊，可调用 create_appointment 提交预约请求（需医生复核后生效）。"
        ),
    },
    "knowledge": {
        "label": "知识智能体",
        "allowed_tools": ["search_knowledge"],
        "system_prompt": (
            "你是医智助手的【知识智能体】。依据医学知识库回答疾病、症状、用药、护理等健康问答。"
            "必须先调用 search_knowledge 检索，禁止凭空编造；使用中文序号分点，通俗易懂。"
        ),
    },
}

DEFAULT_ROLE = "knowledge"


def classify_role(question: str, user_role: str = "public") -> str:
    """轻量 Supervisor：关键词启发式路由（离线可用，不依赖大模型）。

    在线模式可改用 LLM 分类；这里保持无模型依赖，确保全链路可用。
    """
    question = question or ""

    # 医护身份 + 涉及患者/病历/住院/预约 → 对应工作智能体
    if user_role in ("doctor", "nurse", "admin") and any(
        k in question for k in ["患者", "住院", "病历", "预约", "诊断", "查房", "医嘱"]
    ):
        return "doctor" if user_role == "doctor" else "nurse"

    triage_kw = ["挂哪个科", "挂什么科", "看什么科", "去哪个科室", "挂什么号",
                 "应该看", "去哪看病", "分诊", "导诊", "看哪科", "就诊科室"]
    if any(k in question for k in triage_kw):
        return "triage"

    nurse_kw = ["怎么护理", "如何护理", "注意事项", "康复", "术后", "饮食注意",
                "用药指导", "护理要点", "换药", "复查"]
    if any(k in question for k in nurse_kw):
        return "nurse"

    doctor_kw = ["吃什么药", "用什么药", "怎么治", "如何治疗", "诊断", "是什么病",
                 "是不是", "严重吗", "用药", "治疗方案"]
    if any(k in question for k in doctor_kw):
        return "doctor"

    return DEFAULT_ROLE


def get_role(role_key: str) -> dict:
    return ROLES.get(role_key, ROLES[DEFAULT_ROLE])


def allowed_tool_schemas(tool_schemas: list, role_key: str) -> list:
    """按角色白名单过滤工具 schema（在线函数调用用）。"""
    allowed = set(get_role(role_key)["allowed_tools"])
    return [s for s in tool_schemas if s.get("function", {}).get("name") in allowed]
