from flask import Blueprint, current_app, g, request

from services import auth_service
from api.decorators import require_auth
from utils.errors import ApiError

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    role = data.get("role", "")
    display_name = data.get("display_name", "")
    user = auth_service.create_user(username, password, role, display_name)
    token = auth_service.encode_token(user, current_app.config["JWT_SECRET"],
                                      current_app.config["JWT_EXPIRES_HOURS"])
    return {"token": token, "user": user}


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    if not username or not password:
        raise ApiError("请输入用户名和密码", 400)
    user = auth_service.authenticate(username, password)
    token = auth_service.encode_token(user, current_app.config["JWT_SECRET"],
                                      current_app.config["JWT_EXPIRES_HOURS"])
    return {"token": token, "user": user}


@auth_bp.get("/me")
@require_auth
def me():
    return {"user": g.user}
