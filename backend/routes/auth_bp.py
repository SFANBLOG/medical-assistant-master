"""认证路由"""
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash

from backend.services import auth_service
from backend.utils.db import fetchone, fetchall, execute, DB_TYPE
from backend.utils.jwt_utils import login_required, current_user, role_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    result = auth_service.login(username, password)
    if not result:
        return jsonify({"error": "用户名或密码错误"}), 401
    return jsonify(result)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "public")
    display_name = data.get("display_name", "")

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    if len(username) < 3:
        return jsonify({"error": "用户名至少 3 个字符"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码至少 6 个字符"}), 400
    if role not in ("patient", "public"):
        return jsonify({"error": "仅支持注册患者或群众账号"}), 400

    result = auth_service.register(username, password, role, display_name)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    user = current_user()
    info = auth_service.get_user_info(user["user_id"])
    if not info:
        return jsonify({"error": "用户不存在"}), 404
    return jsonify(info)


# ---- 用户管理（管理员）----

@auth_bp.route("/users", methods=["GET"])
@role_required("admin")
def list_users():
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)
    role_filter = request.args.get("role", "")
    offset = (page - 1) * size
    ph = "%s" if DB_TYPE == "mysql" else "?"

    if role_filter:
        total = fetchone("SELECT COUNT(*) AS cnt FROM users WHERE role = %s", (role_filter,))["cnt"]
        rows = fetchall(
            f"SELECT id, username, role, display_name, created_at FROM users "
            f"WHERE role = %s ORDER BY id DESC LIMIT {ph} OFFSET {ph}",
            (role_filter, size, offset)
        )
    else:
        total = fetchone("SELECT COUNT(*) AS cnt FROM users")["cnt"]
        rows = fetchall(
            f"SELECT id, username, role, display_name, created_at FROM users "
            f"ORDER BY id DESC LIMIT {ph} OFFSET {ph}",
            (size, offset)
        )
    return jsonify({"total": total, "list": rows, "page": page, "size": size})


@auth_bp.route("/users", methods=["POST"])
@role_required("admin")
def create_user():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "public")
    display_name = data.get("display_name", "")

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    if role not in ("patient", "doctor", "nurse", "public", "admin"):
        return jsonify({"error": "角色不合法"}), 400

    existing = fetchone("SELECT id FROM users WHERE username = %s", (username,))
    if existing:
        return jsonify({"error": "用户名已存在"}), 400

    pw_hash = generate_password_hash(password)
    execute(
        "INSERT INTO users (username, password_hash, role, display_name) VALUES (%s, %s, %s, %s)",
        (username, pw_hash, role, display_name)
    )
    user = fetchone("SELECT id, username, role, display_name, created_at FROM users WHERE username = %s", (username,))
    return jsonify(user)


@auth_bp.route("/users/<int:user_id>", methods=["DELETE"])
@role_required("admin")
def delete_user(user_id):
    user = fetchone("SELECT role FROM users WHERE id = %s", (user_id,))
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    if user_id == 1:
        return jsonify({"error": "不能删除初始管理员"}), 400

    execute("DELETE FROM users WHERE id = %s", (user_id,))
    return jsonify({"message": "已删除"})


@auth_bp.route("/users/<int:user_id>", methods=["PUT"])
@role_required("admin")
def update_user(user_id):
    data = request.get_json(silent=True) or {}
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
        return jsonify({"error": "没有要更新的字段"}), 400

    values.append(user_id)
    execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", values)
    user = fetchone("SELECT id, username, role, display_name, created_at FROM users WHERE id = %s", (user_id,))
    return jsonify(user)
