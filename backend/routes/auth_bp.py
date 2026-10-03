"""认证路由（FastAPI APIRouter）。"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from werkzeug.security import generate_password_hash

from backend.services import auth_service
from backend.utils.api_utils import json_body
from backend.utils.db import fetchone, fetchall, execute, DB_TYPE
from backend.utils.jwt_utils import get_current_user, require_roles

router = APIRouter()


@router.post("/login")
def login(data: dict = Depends(json_body)):
    username = (data.get("username") or "").strip()
    password = data.get("password", "")
    if not username or not password:
        return JSONResponse({"error": "用户名和密码不能为空"}, status_code=400)

    result = auth_service.login(username, password)
    if not result:
        return JSONResponse({"error": "用户名或密码错误"}, status_code=401)
    return result


@router.post("/register")
def register(data: dict = Depends(json_body)):
    username = (data.get("username") or "").strip()
    password = data.get("password", "")
    role = data.get("role", "public")
    display_name = data.get("display_name", "")

    if not username or not password:
        return JSONResponse({"error": "用户名和密码不能为空"}, status_code=400)
    if len(username) < 3:
        return JSONResponse({"error": "用户名至少 3 个字符"}, status_code=400)
    if len(password) < 6:
        return JSONResponse({"error": "密码至少 6 个字符"}, status_code=400)
    if role not in ("patient", "public"):
        return JSONResponse({"error": "仅支持注册患者或群众账号"}, status_code=400)

    result = auth_service.register(username, password, role, display_name)
    if "error" in result:
        return JSONResponse(result, status_code=400)
    return result


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    info = auth_service.get_user_info(user["user_id"])
    if not info:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    return info


# ---- 用户管理（管理员）----

@router.get("/users")
def list_users(user: dict = Depends(require_roles("admin")),
               page: int = Query(1), size: int = Query(20), role: str = Query("")):
    offset = (page - 1) * size
    ph = "%s" if DB_TYPE == "mysql" else "?"

    if role:
        total = fetchone("SELECT COUNT(*) AS cnt FROM users WHERE role = %s", (role,))["cnt"]
        rows = fetchall(
            f"SELECT id, username, role, display_name, created_at FROM users "
            f"WHERE role = %s ORDER BY id DESC LIMIT {ph} OFFSET {ph}",
            (role, size, offset)
        )
    else:
        total = fetchone("SELECT COUNT(*) AS cnt FROM users")["cnt"]
        rows = fetchall(
            f"SELECT id, username, role, display_name, created_at FROM users "
            f"ORDER BY id DESC LIMIT {ph} OFFSET {ph}",
            (size, offset)
        )
    return {"total": total, "list": rows, "page": page, "size": size}


@router.post("/users")
def create_user(user: dict = Depends(require_roles("admin")),
                data: dict = Depends(json_body)):
    username = (data.get("username") or "").strip()
    password = data.get("password", "")
    role = data.get("role", "public")
    display_name = data.get("display_name", "")

    if not username or not password:
        return JSONResponse({"error": "用户名和密码不能为空"}, status_code=400)
    if role not in ("patient", "doctor", "nurse", "public", "admin"):
        return JSONResponse({"error": "角色不合法"}, status_code=400)

    existing = fetchone("SELECT id FROM users WHERE username = %s", (username,))
    if existing:
        return JSONResponse({"error": "用户名已存在"}, status_code=400)

    pw_hash = generate_password_hash(password)
    execute(
        "INSERT INTO users (username, password_hash, role, display_name) VALUES (%s, %s, %s, %s)",
        (username, pw_hash, role, display_name)
    )
    user_row = fetchone("SELECT id, username, role, display_name, created_at FROM users WHERE username = %s", (username,))
    return user_row


@router.delete("/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(require_roles("admin"))):
    row = fetchone("SELECT role FROM users WHERE id = %s", (user_id,))
    if not row:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    if user_id == 1:
        return JSONResponse({"error": "不能删除初始管理员"}, status_code=400)

    execute("DELETE FROM users WHERE id = %s", (user_id,))
    return {"message": "已删除"}


@router.put("/users/{user_id}")
def update_user(user_id: int, user: dict = Depends(require_roles("admin")),
                data: dict = Depends(json_body)):
    fields = []
    values = []

    if "display_name" in data:
        fields.append("display_name = %s")
        values.append(data["display_name"])
    if "role" in data and data["role"] in ("patient", "doctor", "nurse", "public", "admin"):
        fields.append("role = %s")
        values.append(data["role"])
    if "password" in data and data["password"]:
        fields.append("password_hash = %s")
        values.append(generate_password_hash(data["password"]))

    if not fields:
        return JSONResponse({"error": "没有要更新的字段"}, status_code=400)

    values.append(user_id)
    execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", values)
    user_row = fetchone("SELECT id, username, role, display_name, created_at FROM users WHERE id = %s", (user_id,))
    return user_row
