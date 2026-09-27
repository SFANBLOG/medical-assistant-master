"""RAG 上下文增强：长期记忆（用户画像注入）。

在每次回答前，自动检索当前用户的长期背景（身份、近期诊断、在院/预约），
注入到系统提示中，满足医疗场景的个性化与安全需求，
例如「该患者有青霉素过敏」——这是医疗安全的硬需求。
"""
from backend.utils.db import fetchall, fetchone


def get_user_context(state: dict) -> str:
    """返回当前用户的长期记忆片段（供系统提示注入）。

    包含：身份、近期住院诊断、近期预约。无信息时返回空串。
    """
    user_id = state.get("user_id")
    if not user_id:
        return ""
    try:
        u = fetchone("SELECT id, name, role FROM users WHERE id = %s", (user_id,))
        if not u:
            return ""
        parts = [f"当前用户：{u.get('name', '用户')}（身份：{u.get('role', '未知')}）"]

        rows = fetchall(
            "SELECT diagnosis, department, admit_date FROM hospitalizations "
            "WHERE patient_id = %s ORDER BY admit_date DESC LIMIT 3",
            (user_id,),
        )
        if rows:
            diag = "；".join(
                f"{r.get('diagnosis', '?')}（{r.get('department', '')}，{r.get('admit_date')}）"
                for r in rows
            )
            parts.append(f"近期病史：{diag}")

        aps = fetchall(
            "SELECT department, appointment_time, status FROM appointments "
            "WHERE patient_id = %s ORDER BY appointment_time DESC LIMIT 3",
            (user_id,),
        )
        if aps:
            ap = "；".join(
                f"{r.get('department', '')}（{r.get('appointment_time')}，{r.get('status', '')}）"
                for r in aps
            )
            parts.append(f"近期预约：{ap}")

        return "【用户长期记忆】" + "。".join(parts) + "。"
    except Exception:  # noqa: BLE001
        return ""


def get_enhanced_user_context(state: dict) -> str:
    """增强版用户画像（在 get_user_context 基础上扩展）。

    新增：
      - 上次咨询摘要（最近一条 assistant 消息的前 100 字）
    """
    base = get_user_context(state)
    if not base:
        return base

    user_id = state.get("user_id")
    if not user_id:
        return base

    extras = []

    # 上次咨询摘要
    try:
        last_msg = fetchone(
            "SELECT content FROM messages WHERE conversation_id IN "
            "(SELECT id FROM conversations WHERE user_id = %s) "
            "AND role = 'assistant' ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        if last_msg and last_msg.get("content"):
            summary = last_msg["content"][:100].strip()
            extras.append(f"上次咨询摘要：{summary}...")
    except Exception:
        pass

    if extras:
        return base + "【补充信息】" + "。".join(extras) + "。"
    return base
