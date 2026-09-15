"""API 公共工具：JWT 鉴权、错误响应。"""
from functools import wraps

from flask import jsonify, request

import config as cfg
from services import auth as auth_svc


def get_token():
    h = request.headers.get("Authorization", "")
    if h.startswith("Bearer "):
        return h[7:]
    return h or request.args.get("token")


def current_user():
    token = get_token()
    if not token:
        return None
    payload = auth_svc.decode_token(token)
    if not payload:
        return None
    return auth_svc.get_user_by_id(payload["uid"])


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u:
            return jsonify({"error": "未认证或登录已过期"}), 401
        request.user = u
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            u = current_user()
            if not u:
                return jsonify({"error": "未认证或登录已过期"}), 401
            if u["role"] not in roles:
                return jsonify({"error": "无权限执行该操作"}), 403
            request.user = u
            return f(*args, **kwargs)
        return wrapper
    return decorator


def ok(data=None, **kw):
    return jsonify({"ok": True, "data": data, **kw})


def fail(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code
