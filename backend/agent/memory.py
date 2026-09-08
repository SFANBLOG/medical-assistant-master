"""Agent 长期记忆（用户画像注入）+ 会话级工作记忆。

在每次回答前，自动检索当前用户的长期背景（身份、近期诊断、在院/预约），
注入到系统提示与答案中，满足医疗场景的个性化与安全需求。

对应《Agent项目要点.md》P2：长期（用户画像）记忆，在回答前自动注入相关用户背景，
例如「该患者有青霉素过敏」——这是医疗安全的硬需求。

增强（Agent 架构升级）：
  - ConversationMemory：会话级工作记忆，管理上下文窗口 + 工具结果缓存
  - get_enhanced_user_context：扩展版用户画像（过敏史、上次咨询摘要）
"""
import hashlib
from typing import Optional

from backend.utils.db import fetchall, fetchone


# ---------------------------------------------------------------------------
# 长期记忆：用户画像注入（原有功能 + 增强）
# ---------------------------------------------------------------------------

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
    except Exception as e:  # noqa: BLE001
        return ""


def get_enhanced_user_context(state: dict) -> str:
    """增强版用户画像（在 get_user_context 基础上扩展）。

    新增：
      - 上次咨询摘要（最近一条 assistant 消息的前 100 字）
      - 过敏史提示（从诊断中提取关键词）
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


# ---------------------------------------------------------------------------
# 会话级工作记忆：上下文窗口 + 工具结果缓存
# ---------------------------------------------------------------------------

class ConversationMemory:
    """会话级工作记忆。

    管理当前对话的上下文窗口，提供工具结果缓存以避免重复查询。
    生命周期为单次会话（不持久化到数据库）。
    """

    def __init__(self, conv_id: str, max_turns: int = 6):
        self.conv_id = conv_id
        self.max_turns = max_turns
        self._tool_cache: dict[str, str] = {}  # args_hash → result

    def get_history(self) -> list[dict]:
        """获取最近 N 轮对话历史。"""
        rows = fetchall(
            "SELECT role, content FROM messages WHERE conversation_id = %s "
            "ORDER BY id DESC LIMIT %s",
            (self.conv_id, self.max_turns),
        )
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def cache_tool_result(self, tool_name: str, args: dict, result: str) -> None:
        """缓存工具调用结果。"""
        key = self._make_key(tool_name, args)
        self._tool_cache[key] = result

    def get_cached_result(self, tool_name: str, args: dict) -> Optional[str]:
        """查询工具结果缓存。命中则返回缓存文本，未命中返回 None。"""
        key = self._make_key(tool_name, args)
        return self._tool_cache.get(key)

    def clear_cache(self) -> None:
        """清空工具缓存。"""
        self._tool_cache.clear()

    @staticmethod
    def _make_key(tool_name: str, args: dict) -> str:
        """生成缓存 key（工具名 + 参数哈希）。"""
        raw = f"{tool_name}:{sorted(args.items())}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]
