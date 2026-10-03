"""医疗业务路由（FastAPI APIRouter）。"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from backend.services import medical_service
from backend.utils.api_utils import json_body
from backend.utils.jwt_utils import get_current_user, require_roles

router = APIRouter()


# ---- 住院信息 ----

@router.get("/hospitalizations")
def list_hospitalizations(user: dict = Depends(get_current_user),
                          page: int = Query(1), size: int = Query(20),
                          patient_id: int | None = Query(None)):
    # 患者/群众只能查自己
    if user["role"] in ("patient", "public"):
        return medical_service.list_hospitalizations(user["user_id"], page, size)
    return medical_service.list_hospitalizations(patient_id, page, size)


@router.post("/hospitalizations")
def create_hospitalization(user: dict = Depends(require_roles("doctor", "admin")),
                           data: dict = Depends(json_body)):
    return medical_service.create_hospitalization(data)


@router.put("/hospitalizations/{hosp_id}")
def update_hospitalization(hosp_id: int, user: dict = Depends(require_roles("doctor", "admin")),
                           data: dict = Depends(json_body)):
    return medical_service.update_hospitalization(hosp_id, data)


# ---- 消费明细 ----

@router.get("/bills")
def list_bills(user: dict = Depends(get_current_user),
               page: int = Query(1), size: int = Query(20),
               patient_id: int | None = Query(None)):
    if user["role"] in ("patient", "public"):
        return medical_service.list_bills(user["user_id"], page, size)
    return medical_service.list_bills(patient_id, page, size)


# ---- 预约挂号 ----

@router.get("/appointments")
def list_appointments(user: dict = Depends(get_current_user),
                      page: int = Query(1), size: int = Query(20),
                      patient_id: int | None = Query(None)):
    if user["role"] in ("patient", "public"):
        return medical_service.list_appointments(user["user_id"], page, size)
    return medical_service.list_appointments(patient_id, page, size)


@router.post("/appointments")
def create_appointment(user: dict = Depends(get_current_user),
                       data: dict = Depends(json_body)):
    # 患者自动绑定自己
    if user["role"] in ("patient", "public"):
        data["patient_id"] = user["user_id"]

    if not data.get("department") or not data.get("date") or not data.get("time_slot"):
        return JSONResponse({"error": "科室、日期和时间段不能为空"}, status_code=400)

    return medical_service.create_appointment(data)


@router.put("/appointments/{appt_id}")
def update_appointment(appt_id: int, user: dict = Depends(require_roles("doctor", "admin")),
                       data: dict = Depends(json_body)):
    return medical_service.update_appointment(appt_id, data)


# ---- 护理记录 ----

@router.get("/nursing-records")
def list_nursing_records(user: dict = Depends(get_current_user),
                         page: int = Query(1), size: int = Query(20),
                         patient_id: int | None = Query(None)):
    if user["role"] == "patient":
        return medical_service.list_nursing_records(user["user_id"], page, size)
    return medical_service.list_nursing_records(patient_id, page, size)


@router.post("/nursing-records")
def create_nursing_record(user: dict = Depends(require_roles("nurse", "doctor", "admin")),
                          data: dict = Depends(json_body)):
    # 护士自动绑定自己
    if user["role"] == "nurse":
        data["nurse_id"] = user["user_id"]

    if not data.get("patient_id") or not data.get("content"):
        return JSONResponse({"error": "患者ID和内容不能为空"}, status_code=400)

    return medical_service.create_nursing_record(data)


# ---- 排班 ----

@router.get("/schedules")
def list_schedules(user: dict = Depends(get_current_user),
                   page: int = Query(1), size: int = Query(20),
                   staff_id: int | None = Query(None)):
    if user["role"] in ("doctor", "nurse"):
        return medical_service.list_schedules(user["user_id"], page, size)
    return medical_service.list_schedules(staff_id, page, size)


@router.post("/schedules")
def create_schedule(user: dict = Depends(require_roles("doctor", "admin")),
                    data: dict = Depends(json_body)):
    if not data.get("staff_id") or not data.get("work_date") or not data.get("shift"):
        return JSONResponse({"error": "人员、日期和班次不能为空"}, status_code=400)
    return medical_service.create_schedule(data)
