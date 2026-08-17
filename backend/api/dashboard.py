from flask import Blueprint, g

from api.decorators import require_auth, require_roles
from models.db import get_conn

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/stats")
@require_auth
def stats():
    conn = get_conn()
    user = g.user
    # 医生/管理员可见全系统数据；其余角色仅本人可见范围
    is_staff = user["role"] in ("doctor", "admin")

    if is_staff:
        kb_scope = ""  # 全系统
        params: tuple = ()
    else:
        kb_scope = "WHERE visibility='public' OR owner_id=?"
        params = (user["id"],)

    kb_count = conn.execute(
        f"SELECT COUNT(*) FROM knowledge_bases {kb_scope}", params
    ).fetchone()[0]
    doc_count = conn.execute(
        f"""SELECT COALESCE(SUM(doc_count),0) FROM
            (SELECT (SELECT COUNT(*) FROM documents d WHERE d.kb_id=k.id) AS doc_count
             FROM knowledge_bases k {kb_scope})""",
        params,
    ).fetchone()[0]
    chunk_count = conn.execute(
        f"""SELECT COALESCE(SUM(chunk_count),0) FROM
            (SELECT (SELECT COALESCE(SUM(d.chunk_count),0) FROM documents d WHERE d.kb_id=k.id) AS chunk_count
             FROM knowledge_bases k {kb_scope})""",
        params,
    ).fetchone()[0]

    if is_staff:
        conv_scope, conv_params = "", ()
    else:
        conv_scope, conv_params = "WHERE user_id=?", (user["id"],)
    conv_count = conn.execute(
        f"SELECT COUNT(*) FROM conversations {conv_scope}", conv_params
    ).fetchone()[0]
    msg_count = conn.execute(
        f"SELECT COUNT(*) FROM messages WHERE conversation_id IN (SELECT id FROM conversations {conv_scope})",
        conv_params,
    ).fetchone()[0]

    docs_by_kb = [
        dict(r)
        for r in conn.execute(
            f"""SELECT k.name, (SELECT COUNT(*) FROM documents d WHERE d.kb_id=k.id) AS doc_count
                FROM knowledge_bases k {kb_scope} ORDER BY doc_count DESC LIMIT 10""",
            params,
        ).fetchall()
    ]
    result = {
        "kb_count": kb_count,
        "doc_count": doc_count,
        "chunk_count": chunk_count,
        "conversation_count": conv_count,
        "message_count": msg_count,
        "docs_by_kb": docs_by_kb,
        "role": user["role"],
    }
    if is_staff:
        result["role_breakdown"] = [
            dict(r)
            for r in conn.execute(
                "SELECT role, COUNT(*) AS count FROM users GROUP BY role"
            ).fetchall()
        ]
    return result


@dashboard_bp.get("/recent")
@require_roles("doctor", "admin")
def recent():
    conn = get_conn()
    rows = conn.execute(
        """SELECT c.id, c.title, c.created_at, u.username, u.role, k.name AS kb_name
           FROM conversations c
           JOIN users u ON u.id = c.user_id
           LEFT JOIN knowledge_bases k ON k.id = c.kb_id
           ORDER BY c.updated_at DESC LIMIT 20"""
    ).fetchall()
    return {"items": [dict(r) for r in rows]}
