"""RAG 上下文增强：长期记忆（用户画像注入）。

在每次回答前，按当前登录用户的**角色权限**检索其长期背景（身份、近期病史、
近期血糖、在院/预约、上次咨询摘要），注入到系统提示中，使「同一个问题在不同
患者身上给出不同表述」成为可能——例如糖尿病患者问「能不能吃粥」，回答会带上其
近期血糖读数，这是医疗场景的个性化与安全硬需求。

安全设计：
- **注入受角色权限约束**：只有具备临床知情权的角色（patient/doctor/nurse）才会
  被注入病史/血糖/预约/上次咨询摘要等临床字段；public/admin 仅注入身份，遵循
  最小必要原则（管理员不得在提示里静默获取患者临床细节）。
- **日志不保留原文**：本模块只负责拼出注入文本，另返回一份**脱敏元信息**
  （字段类别 + 条数 + 字符数，绝不含任何原始病历/血糖数值），供审计留痕使用。
  原始画像文本仅在内存里拼进请求发给 LLM，本身不落库、不写日志。
"""
from backend.utils.db import fetchall, fetchone

# 具备临床知情权、可被注入病史/血糖/预约/上次咨询摘要的角色。
# public（未登录群众口径）与 admin（平台运维）均不注入临床字段。
_CLINICAL_INJECTION_ROLES = {"patient", "doctor", "nurse"}

# 血糖指标名（与 health_metrics.metric 对应）
_GLUCOSE_METRIC = "blood_glucose"


def _recent_glucose(user_id: int, limit: int = 3) -> list[dict]:
    """取该患者最近的血糖读数（结构化体征表 health_metrics）。"""
    return fetchall(
        "SELECT value, unit, context, recorded_at FROM health_metrics "
        "WHERE patient_id = %s AND metric = %s "
        f"ORDER BY recorded_at DESC LIMIT {int(limit)}",
        (user_id, _GLUCOSE_METRIC),
    )


def build_user_profile(state: dict) -> tuple[str, dict]:
    """构建当前用户的画像注入片段 + 脱敏元信息。

    Args:
        state: {"user_id": int, "role": str}。role 为发起本次问答的登录用户角色，
               用于角色权限门控。

    Returns:
        (text, meta)
        - text：注入系统提示的画像文本；无内容时为 ""。
        - meta：**脱敏**审计信息，仅含 role / 注入的字段类别 fields / 各类条数
                counts / 文本字符数 chars，绝不包含任何原始病历、血糖数值或姓名。
    """
    user_id = state.get("user_id")
    role = (state.get("role") or "").lower()
    meta: dict = {"role": role, "fields": [], "counts": {}, "chars": 0}
    if not user_id:
        return "", meta

    try:
        u = fetchone("SELECT id, display_name, role FROM users WHERE id = %s", (user_id,))
        if not u:
            return "", meta

        parts: list[str] = []
        # 身份：所有角色都可注入（不含敏感临床信息）
        parts.append(f"当前用户：{u.get('display_name') or '用户'}（身份：{u.get('role', '未知')}）")
        meta["fields"].append("identity")

        # 以下临床字段受角色权限约束：仅知情角色注入
        if role in _CLINICAL_INJECTION_ROLES:
            rows = fetchall(
                "SELECT diagnosis, department, admit_date FROM hospitalizations "
                "WHERE patient_id = %s ORDER BY admit_date DESC LIMIT 3",
                (user_id,),
            )
            if rows:
                diag = "；".join(
                    f"{r.get('diagnosis') or '?'}（{r.get('department', '')}，{r.get('admit_date')}）"
                    for r in rows
                )
                parts.append(f"近期病史：{diag}")
                meta["fields"].append("recent_history")
                meta["counts"]["recent_history"] = len(rows)

            glucose = _recent_glucose(user_id)
            if glucose:
                gtxt = "；".join(
                    f"{r.get('value')}{r.get('unit', '')}"
                    + (f"（{r.get('context')}）" if r.get("context") else "")
                    + f"，{r.get('recorded_at')}"
                    for r in glucose
                )
                parts.append(f"近期血糖：{gtxt}")
                meta["fields"].append("glucose")
                meta["counts"]["glucose"] = len(glucose)

            aps = fetchall(
                "SELECT department, date, time_slot, status FROM appointments "
                "WHERE patient_id = %s ORDER BY date DESC LIMIT 3",
                (user_id,),
            )
            if aps:
                ap = "；".join(
                    f"{r.get('department', '')}（{r.get('date')} {r.get('time_slot', '')}，{r.get('status', '')}）"
                    for r in aps
                )
                parts.append(f"近期预约：{ap}")
                meta["fields"].append("appointments")
                meta["counts"]["appointments"] = len(aps)

            # 上次咨询摘要：最近一条 assistant 消息的前 100 字
            last_msg = fetchone(
                "SELECT content FROM messages WHERE conversation_id IN "
                "(SELECT id FROM conversations WHERE user_id = %s) "
                "AND role = 'assistant' ORDER BY id DESC LIMIT 1",
                (user_id,),
            )
            if last_msg and last_msg.get("content"):
                summary = last_msg["content"][:100].strip()
                parts.append(f"上次咨询摘要：{summary}...")
                meta["fields"].append("last_summary")
                meta["counts"]["last_summary"] = 1

        text = "【用户长期记忆】" + "。".join(parts) + "。"
        meta["chars"] = len(text)
        return text, meta
    except Exception:  # noqa: BLE001 画像构建失败绝不阻断问答
        return "", {"role": role, "fields": [], "counts": {}, "chars": 0}


def get_user_context(state: dict) -> str:
    """兼容旧接口：仅返回画像文本（不含上次咨询摘要）。

    新代码请使用 build_user_profile()，可同时拿到脱敏审计元信息。
    """
    role = (state.get("role") or "").lower()
    text, _ = build_user_profile({"user_id": state.get("user_id"), "role": role})
    return text


def get_enhanced_user_context(state: dict) -> str:
    """兼容旧接口：返回完整画像文本（含上次咨询摘要，按角色门控）。"""
    text, _ = build_user_profile(state)
    return text
