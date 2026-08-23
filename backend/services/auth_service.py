"""认证服务：用户创建/校验、JWT 编解码。"""
import datetime
from typing import Optional

import jwt
from models.db import get_conn
from utils.errors import ApiError
from werkzeug.security import check_password_hash, generate_password_hash

VALID_ROLES = ("patient", "doctor", "nurse", "public", "admin")


def create_user(username: str, password: str, role: str, display_name: str = "") -> dict:
    if role not in VALID_ROLES:
        raise ApiError("无效的用户身份", 400)
    username = username.strip()
    if not (3 <= len(username) <= 32):
        raise ApiError("用户名长度需在 3-32 个字符之间", 400)
    if len(password) < 6:
        raise ApiError("密码长度至少 6 位", 400)

    conn = get_conn()
    exists = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
    if exists:
        raise ApiError("用户名已存在", 409)
    display_name = display_name.strip() or username
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, ?, ?)",
        (username, generate_password_hash(password), role, display_name),
    )
    conn.commit()
    return user_to_dict(conn, cur.lastrowid)


def authenticate(username: str, password: str) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        raise ApiError("用户名或密码错误", 401)
    # 仅返回安全字段，绝不下发 password_hash
    return user_to_dict(conn, row["id"])


def user_to_dict(conn, user_id: int) -> dict:
    row = conn.execute(
        "SELECT id, username, role, display_name, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        raise ApiError("用户不存在", 404)
    return dict(row)


def encode_token(user: dict, secret: str, expires_hours: int = 24) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user["id"]),  # JWT 规范要求 subject 为字符串
        "role": user["role"],
        "username": user["username"],
        "iat": now,
        "exp": now + datetime.timedelta(hours=expires_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> Optional[dict]:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
