"""护士端 API：患者信息、护理记录。"""
from flask import Blueprint, g, request

from api.decorators import require_roles
from services import nurse_service

nurse_bp = Blueprint("nurse", __name__)


@nurse_bp.get("/patients")
@require_roles("nurse")
def patients():
    return {"items": nurse_service.list_patients(request.args.get("q", ""))}


@nurse_bp.get("/nursing-records")
@require_roles("nurse")
def nursing_records():
    pid = int(request.args.get("patient_id", "0") or 0)
    return {"items": nurse_service.list_nursing_records(pid)}


@nurse_bp.post("/nursing-records")
@require_roles("nurse")
def create_record():
    data = request.get_json(silent=True) or {}
    r = nurse_service.create_nursing_record(
        nurse_id=g.user["id"],
        patient_id=int(data.get("patient_id", 0) or 0),
        content=data.get("content", ""),
        record_type=data.get("record_type", "daily"),
        recorded_at=data.get("recorded_at", ""),
    )
    return r, 201
