"""仪表盘路由"""
from flask import Blueprint, jsonify

from backend.services import dashboard_service
from backend.utils.jwt_utils import login_required, current_user, role_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/overview", methods=["GET"])
@login_required
def overview():
    """系统总览（管理员可见完整数据，其他角色看精简版）。"""
    user = current_user()
    if user["role"] == "admin":
        return jsonify(dashboard_service.get_system_overview())
    elif user["role"] in ("patient", "public"):
        return jsonify(dashboard_service.get_patient_overview(user["user_id"]))
    else:
        # 医生/护士看业务统计
        return jsonify({
            "business": dashboard_service.get_business_stats(),
            "chat": dashboard_service.get_chat_stats(),
        })


@dashboard_bp.route("/users", methods=["GET"])
@role_required("admin")
def user_stats():
    return jsonify(dashboard_service.get_user_stats())


@dashboard_bp.route("/knowledge-bases", methods=["GET"])
@login_required
def kb_stats():
    return jsonify(dashboard_service.get_kb_stats())


@dashboard_bp.route("/business", methods=["GET"])
@role_required("doctor", "admin")
def business_stats():
    return jsonify(dashboard_service.get_business_stats())


@dashboard_bp.route("/chat", methods=["GET"])
@login_required
def chat_stats():
    return jsonify(dashboard_service.get_chat_stats())


@dashboard_bp.route("/revenue", methods=["GET"])
@role_required("admin", "doctor")
def revenue_stats():
    return jsonify(dashboard_service.get_revenue_stats())


@dashboard_bp.route("/department-distribution", methods=["GET"])
@role_required("doctor", "admin")
def dept_distribution():
    return jsonify(dashboard_service.get_department_distribution())


@dashboard_bp.route("/bill-category-distribution", methods=["GET"])
@role_required("admin", "doctor")
def bill_category_distribution():
    return jsonify(dashboard_service.get_bill_category_distribution())
