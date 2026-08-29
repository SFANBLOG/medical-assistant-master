"""认证相关装饰器与健康检查。"""
from functools import wraps

from flask import Blueprint, g, request
from models.db import get_conn
from services.auth_service import decode_token
from utils.errors import ApiError

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
def health():
    return {"status": "ok"}


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise ApiError("未登录或登录已过期", 401)
        from flask import current_app

        payload = decode_token(header[7:], current_app.config["JWT_SECRET"])
        if not payload:
            raise ApiError("未登录或登录已过期", 401)
        conn = get_conn()
        row = conn.execute(
            "SELECT id, username, role, display_name FROM users WHERE id=?",
            (int(payload["sub"]),),
        ).fetchone()
        if not row:
            raise ApiError("用户不存在", 401)
        g.user = dict(row)
        return fn(*args, **kwargs)

    return wrapper


def require_roles(*roles):
    def deco(fn):
        @wraps(fn)
        @require_auth
        def wrapper(*args, **kwargs):
            if g.user["role"] not in roles:
                raise ApiError("当前身份无权执行此操作", 403)
            return fn(*args, **kwargs)

        return wrapper

    return deco
