"""认证接口。"""
from flask import Blueprint, request

from models import db
from services import auth as auth_svc
from api.common import ok, fail, token_required, current_user

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or not password:
        return fail("用户名与密码不能为空")
    res = auth_svc.login(username, password)
    if not res:
        return fail("用户名或密码错误", 401)
    return ok(res)


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    u = current_user()
    return ok({
        "id": u["id"], "username": u["username"],
        "role": u["role"], "display_name": u["display_name"],
    })
