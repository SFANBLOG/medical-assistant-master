"""
JWT 认证工具：签发与验证 token。
"""
import datetime
import functools

import jwt
from flask import request, jsonify, g

from backend.config import JWT_SECRET, JWT_EXP_HOURS


def create_token(user_id: int, username: str, role: str) -> str:
    """签发 JWT。"""
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXP_HOURS),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """解码 JWT，失败返回 None。"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_token_from_request():
    """从 Authorization 头提取 token。"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def login_required(f):
    """装饰器：要求登录。"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token = get_token_from_request()
        if not token:
            return jsonify({"error": "未提供认证令牌"}), 401
        payload = decode_token(token)
        if not payload:
            return jsonify({"error": "认证令牌无效或已过期"}), 401
        g.current_user = payload
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """装饰器：要求特定角色。"""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            token = get_token_from_request()
            if not token:
                return jsonify({"error": "未提供认证令牌"}), 401
            payload = decode_token(token)
            if not payload:
                return jsonify({"error": "认证令牌无效或已过期"}), 401
            if payload.get("role") not in roles:
                return jsonify({"error": "权限不足"}), 403
            g.current_user = payload
            return f(*args, **kwargs)
        return wrapper
    return decorator


def current_user() -> dict | None:
    """获取当前登录用户信息。"""
    return getattr(g, "current_user", None)
