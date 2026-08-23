"""系统管理员 API：用户管理、全系统统计。"""
from api.decorators import require_roles
from flask import Blueprint, request
from services import admin_service

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/users")
@require_roles("admin")
def users():
    role = request.args.get("role", "")
    q = request.args.get("q", "")
    page = max(int(request.args.get("page", "1")), 1)
    page_size = min(max(int(request.args.get("page_size", "10")), 1), 50)
    return admin_service.list_users(role, q, page, page_size)


@admin_bp.post("/users")
@require_roles("admin")
def create_user():
    data = request.get_json(silent=True) or {}
    user = admin_service.create_user(
        data.get("username", ""),
        data.get("password", ""),
        data.get("role", ""),
        data.get("display_name", ""),
    )
    return user, 201


@admin_bp.put("/users/<int:uid>")
@require_roles("admin")
def update_user(uid: int):
    data = request.get_json(silent=True) or {}
    return admin_service.update_user(
        uid,
        role=data.get("role", ""),
        display_name=data.get("display_name", ""),
        reset_password=data.get("reset_password", ""),
    )


@admin_bp.delete("/users/<int:uid>")
@require_roles("admin")
def delete_user(uid: int):
    admin_service.delete_user(uid)
    return {"ok": True}


@admin_bp.get("/stats")
@require_roles("admin")
def stats():
    return admin_service.stats()
