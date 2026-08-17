"""系统管理员服务：用户管理、全系统统计。"""
from models.db import get_conn
from services import auth_service
from utils.errors import ApiError


def list_users(role: str = "", q: str = "", page: int = 1, page_size: int = 10) -> dict:
    conn = get_conn()
    where, params = ["1=1"], []
    if role:
        where.append("role = ?")
        params.append(role)
    if q:
        where.append("(username LIKE ? OR display_name LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    total = conn.execute(
        f"SELECT COUNT(*) FROM users WHERE {' AND '.join(where)}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"""SELECT id, username, role, display_name, created_at FROM users
            WHERE {' AND '.join(where)}
            ORDER BY id LIMIT ? OFFSET ?""",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return {"total": total, "items": [dict(r) for r in rows]}


def create_user(username: str, password: str, role: str, display_name: str = "") -> dict:
    return auth_service.create_user(username, password, role, display_name)


def update_user(uid: int, role: str = "", display_name: str = "", reset_password: str = "") -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not row:
        raise ApiError("用户不存在", 404)
    sets, params = [], []
    if role:
        if role not in auth_service.VALID_ROLES:
            raise ApiError("无效的用户身份", 400)
        sets.append("role = ?")
        params.append(role)
    if display_name:
        sets.append("display_name = ?")
        params.append(display_name)
    if reset_password:
        if len(reset_password) < 6:
            raise ApiError("密码长度至少 6 位", 400)
        from werkzeug.security import generate_password_hash

        sets.append("password_hash = ?")
        params.append(generate_password_hash(reset_password))
    if sets:
        params.append(uid)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
    return auth_service.user_to_dict(conn, uid)


def delete_user(uid: int) -> None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not row:
        raise ApiError("用户不存在", 404)
    if row["role"] == "admin" and row["username"] in ("admindemo",):
        raise ApiError("内置演示管理员账号不可删除", 400)
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()


def stats() -> dict:
    """全系统统计（与 dashboard.stats 的 doctor/admin 语义一致）。"""
    conn = get_conn()

    def count(sql: str, params=()) -> int:
        return conn.execute(sql, params).fetchone()[0]

    kb_count = count("SELECT COUNT(*) FROM knowledge_bases")
    doc_count = count("SELECT COUNT(*) FROM documents")
    chunk_count = count("SELECT COALESCE(SUM(chunk_count),0) FROM documents")
    conv_count = count("SELECT COUNT(*) FROM conversations")
    msg_count = count("SELECT COUNT(*) FROM messages")
    user_count = count("SELECT COUNT(*) FROM users")
    hosp_count = count("SELECT COUNT(*) FROM hospitalizations")
    bill_total = count("SELECT COALESCE(SUM(amount),0) FROM bills")
    role_breakdown = [
        dict(r)
        for r in conn.execute("SELECT role, COUNT(*) AS count FROM users GROUP BY role").fetchall()
    ]
    docs_by_kb = [
        dict(r)
        for r in conn.execute(
            """SELECT k.name, (SELECT COUNT(*) FROM documents d WHERE d.kb_id=k.id) AS doc_count
               FROM knowledge_bases k ORDER BY doc_count DESC LIMIT 10"""
        ).fetchall()
    ]
    return {
        "user_count": user_count,
        "kb_count": kb_count,
        "doc_count": doc_count,
        "chunk_count": chunk_count,
        "conversation_count": conv_count,
        "message_count": msg_count,
        "hospitalization_count": hosp_count,
        "bill_total": round(bill_total, 2),
        "docs_by_kb": docs_by_kb,
        "role_breakdown": role_breakdown,
    }
