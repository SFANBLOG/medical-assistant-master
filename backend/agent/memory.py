"""Agent 长期记忆（用户画像注入）。

在每次回答前，自动检索当前用户的长期背景（身份、近期诊断、在院/预约），
注入到系统提示与答案中，满足医疗场景的个性化与安全需求。

对应《Agent项目要点.md》P2：长期（用户画像）记忆，在回答前自动注入相关用户背景，
例如「该患者有青霉素过敏」——这是医疗安全的硬需求。
"""
from typing import Optional

from backend.utils.db import fetchall, fetchone


def get_user_context(state: dict) -> str:
    """返回当前用户的长期记忆片段（供系统提示/答案注入）。

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
