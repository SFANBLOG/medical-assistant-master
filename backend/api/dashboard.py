"""数据仪表盘 / 系统统计。"""
from flask import Blueprint

import config as cfg
from models import db
from api.common import ok, token_required, current_user

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.route("/stats", methods=["GET"])
@token_required
def stats():
    u = current_user()
    tables = ["knowledge_bases", "documents", "conversations", "messages",
              "hospitalizations", "bills", "appointments", "nursing_records", "schedules"]
    data = {}
    for t in tables:
        try:
            data[t] = db.count(f"SELECT * FROM {t}")
        except Exception:
            data[t] = 0
    # 角色相关摘要
    data["role"] = u["role"]
    if u["role"] == "patient":
        data["my_hospitalizations"] = db.count(
            "SELECT * FROM hospitalizations WHERE patient_id=%s", (u["id"],))
        data["my_bills"] = db.count(
            "SELECT * FROM bills WHERE patient_id=%s", (u["id"],))
    return ok(data)
