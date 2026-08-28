"""
认证服务：登录、注册、用户信息。
"""
from werkzeug.security import check_password_hash

from backend.utils.db import fetchone, execute
from backend.utils.jwt_utils import create_token
from backend import config
def login(username: str, password: str) -> dict | None:
    """用户登录，返回 token 和用户信息，失败返回 None。"""
    user = fetchone("SELECT * FROM users WHERE username = %s", (username,))
    if not user:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    token = create_token(user["id"], user["username"], user["role"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "display_name": user.get("display_name"),
        }
    }


def register(username: str, password: str, role: str = "public", display_name: str = None) -> dict:
    """用户注册。"""
    existing = fetchone("SELECT id FROM users WHERE username = %s", (username,))
    if existing:
        return {"error": "用户名已存在"}

    from werkzeug.security import generate_password_hash
    pw_hash = generate_password_hash(password)
    execute(
        "INSERT INTO users (username, password_hash, role, display_name) VALUES (%s, %s, %s, %s)",
        (username, pw_hash, role, display_name or username)
    )
    user = fetchone("SELECT * FROM users WHERE username = %s", (username,))
    token = create_token(user["id"], user["username"], user["role"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "display_name": user.get("display_name"),
        }
    }


def get_user_info(user_id: int) -> dict | None:
    """获取用户信息。"""
    user = fetchone(
        "SELECT id, username, role, display_name, created_at FROM users WHERE id = %s",
        (user_id,)
    )
    if not user:
        return None
    return dict(user)
