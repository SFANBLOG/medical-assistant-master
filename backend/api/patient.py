"""患者端 API：查询本人住院信息、消费明细、预约挂号。"""
from api.decorators import require_roles
from flask import Blueprint, g, request
from services import patient_service

patient_bp = Blueprint("patient", __name__)


@patient_bp.get("/hospitalizations")
@require_roles("patient")
def my_hospitalizations():
    return {"items": patient_service.list_hospitalizations(g.user["id"])}


@patient_bp.get("/bills")
@require_roles("patient")
def my_bills():
    category = request.args.get("category", "")
    status = request.args.get("status", "")
    return {"items": patient_service.list_bills(g.user["id"], category, status)}


@patient_bp.get("/doctors")
@require_roles("patient", "public")
def doctors():
    from models.db import get_conn

    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, display_name FROM users WHERE role='doctor' ORDER BY id"
    ).fetchall()
    return {"items": [dict(r) for r in rows]}


@patient_bp.get("/appointments")
@require_roles("patient", "public")
def my_appointments():
    return {"items": patient_service.list_appointments(g.user["id"])}


@patient_bp.post("/appointments")
@require_roles("patient", "public")
def create_appointment():
    data = request.get_json(silent=True) or {}
    appt = patient_service.create_appointment(
        g.user["id"],
        department=data.get("department", ""),
        date=data.get("date", ""),
        time_slot=data.get("time_slot", ""),
        doctor_id=data.get("doctor_id"),
        symptom=data.get("symptom", ""),
    )
    return appt, 201


@patient_bp.post("/appointments/<int:appt_id>/cancel")
@require_roles("patient", "public")
def cancel_appointment(appt_id: int):
    patient_service.cancel_appointment(g.user["id"], appt_id)
    return {"ok": True}
