from api.decorators import require_auth
from flask import Blueprint, current_app, g, request
from services import auth_service
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

    # 管理员/医生初次登录：先将知识库清零（删除全部文档/向量/引用），
    # 之后由用户自行上传文档（见前端上传入口）。
    kb_cleared = False
    if user["role"] in ("admin", "doctor"):
        from models.db import get_conn
        from services.kb_service import reset_knowledge_base

        conn = get_conn()
        row = conn.execute(
            "SELECT first_login_done FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
        if row is not None and not row["first_login_done"]:
            # 先置位，避免重置失败导致每次登录反复清空
            conn.execute("UPDATE users SET first_login_done = 1 WHERE id = ?", (user["id"],))
            conn.commit()
            try:
                reset_knowledge_base()
                kb_cleared = True
            except Exception:  # noqa: BLE001 清零失败仅记录，不阻断登录
                current_app.logger.exception("初次登录清空知识库失败")

    return {"token": token, "user": user, "kb_cleared": kb_cleared}


@auth_bp.get("/me")
@require_auth
def me():
    return {"user": g.user}
