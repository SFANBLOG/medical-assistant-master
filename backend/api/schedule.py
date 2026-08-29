"""医护排班 API（医生/护士共用）。"""
from api.decorators import require_roles
from flask import Blueprint, g, request
from services import schedule_service

schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.get("")
@require_roles("doctor", "nurse")
def list_schedules():
    staff_id = request.args.get("staff_id", "")
    department = request.args.get("department", "")
    return {
        "items": schedule_service.list_schedules(
            int(staff_id) if staff_id else 0, department
        )
    }


@schedule_bp.post("")
@require_roles("doctor")
def create_schedule():
    data = request.get_json(silent=True) or {}
    s = schedule_service.create_schedule(
        staff_id=int(data.get("staff_id", g.user["id"])),
        work_date=data.get("work_date", ""),
        shift=data.get("shift", "day"),
        department=data.get("department", ""),
        remark=data.get("remark", ""),
    )
    return s, 201
