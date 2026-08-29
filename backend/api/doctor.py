"""医生端 API：患者管理、住院信息管理。"""
from api.decorators import require_roles
from flask import Blueprint, g, request
from services import doctor_service

doctor_bp = Blueprint("doctor", __name__)


@doctor_bp.get("/patients")
@require_roles("doctor")
def patients():
    q = request.args.get("q", "")
    page = max(int(request.args.get("page", "1")), 1)
    page_size = min(max(int(request.args.get("page_size", "10")), 1), 50)
    return doctor_service.list_patients(q, page, page_size)


@doctor_bp.get("/patients/<int:pid>/hospitalizations")
@require_roles("doctor")
def patient_hospitalizations(pid: int):
    return {"items": doctor_service.list_patient_hospitalizations(pid)}


@doctor_bp.get("/hospitalizations")
@require_roles("doctor")
def hospitalizations():
    status = request.args.get("status", "")
    q = request.args.get("q", "")
    return {"items": doctor_service.list_all_hospitalizations(status, q)}


@doctor_bp.post("/hospitalizations")
@require_roles("doctor")
def create_hospitalization():
    data = request.get_json(silent=True) or {}
    h = doctor_service.create_hospitalization(
        patient_id=int(data.get("patient_id", 0) or 0),
        department=data.get("department", ""),
        admit_date=data.get("admit_date", ""),
        diagnosis=data.get("diagnosis", ""),
        ward=data.get("ward", ""),
        bed_no=data.get("bed_no", ""),
        doctor_id=g.user["id"],
    )
    return h, 201


@doctor_bp.put("/hospitalizations/<int:hid>")
@require_roles("doctor")
def update_hospitalization(hid: int):
    data = request.get_json(silent=True) or {}
    return doctor_service.update_hospitalization(
        hid,
        status=data.get("status", ""),
        discharge_date=data.get("discharge_date", ""),
        diagnosis=data.get("diagnosis", ""),
        total_cost=data.get("total_cost"),
    )
