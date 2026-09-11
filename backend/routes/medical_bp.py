"""医疗业务路由"""
from flask import Blueprint, request, jsonify

from backend.services import medical_service
from backend.utils.jwt_utils import login_required, current_user, role_required

medical_bp = Blueprint("medical", __name__)


# ---- 住院信息 ----

@medical_bp.route("/hospitalizations", methods=["GET"])
@login_required
def list_hospitalizations():
    user = current_user()
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)

    # 患者/群众只能查自己
    if user["role"] in ("patient", "public"):
        result = medical_service.list_hospitalizations(user["user_id"], page, size)
    else:
        patient_id = request.args.get("patient_id", type=int)
        result = medical_service.list_hospitalizations(patient_id, page, size)

    return jsonify(result)


@medical_bp.route("/hospitalizations", methods=["POST"])
@role_required("doctor", "admin")
def create_hospitalization():
    data = request.get_json(silent=True) or {}
    result = medical_service.create_hospitalization(data)
    return jsonify(result)


@medical_bp.route("/hospitalizations/<int:hosp_id>", methods=["PUT"])
@role_required("doctor", "admin")
def update_hospitalization(hosp_id):
    data = request.get_json(silent=True) or {}
    result = medical_service.update_hospitalization(hosp_id, data)
    return jsonify(result)


# ---- 消费明细 ----

@medical_bp.route("/bills", methods=["GET"])
@login_required
def list_bills():
    user = current_user()
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)

    if user["role"] in ("patient", "public"):
        result = medical_service.list_bills(user["user_id"], page, size)
    else:
        patient_id = request.args.get("patient_id", type=int)
        result = medical_service.list_bills(patient_id, page, size)

    return jsonify(result)


# ---- 预约挂号 ----

@medical_bp.route("/appointments", methods=["GET"])
@login_required
def list_appointments():
    user = current_user()
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)

    if user["role"] in ("patient", "public"):
        result = medical_service.list_appointments(user["user_id"], page, size)
    else:
        patient_id = request.args.get("patient_id", type=int)
        result = medical_service.list_appointments(patient_id, page, size)

    return jsonify(result)


@medical_bp.route("/appointments", methods=["POST"])
@login_required
def create_appointment():
    user = current_user()
    data = request.get_json(silent=True) or {}

    # 患者自动绑定自己
    if user["role"] in ("patient", "public"):
        data["patient_id"] = user["user_id"]

    if not data.get("department") or not data.get("date") or not data.get("time_slot"):
        return jsonify({"error": "科室、日期和时间段不能为空"}), 400

    result = medical_service.create_appointment(data)
    return jsonify(result)


@medical_bp.route("/appointments/<int:appt_id>", methods=["PUT"])
@role_required("doctor", "admin")
def update_appointment(appt_id):
    data = request.get_json(silent=True) or {}
    result = medical_service.update_appointment(appt_id, data)
    return jsonify(result)


# ---- 护理记录 ----

@medical_bp.route("/nursing-records", methods=["GET"])
@login_required
def list_nursing_records():
    user = current_user()
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)

    if user["role"] == "patient":
        result = medical_service.list_nursing_records(user["user_id"], page, size)
    else:
        patient_id = request.args.get("patient_id", type=int)
        result = medical_service.list_nursing_records(patient_id, page, size)

    return jsonify(result)


@medical_bp.route("/nursing-records", methods=["POST"])
@role_required("nurse", "doctor", "admin")
def create_nursing_record():
    user = current_user()
    data = request.get_json(silent=True) or {}

    # 护士自动绑定自己
    if user["role"] == "nurse":
        data["nurse_id"] = user["user_id"]

    if not data.get("patient_id") or not data.get("content"):
        return jsonify({"error": "患者ID和内容不能为空"}), 400

    result = medical_service.create_nursing_record(data)
    return jsonify(result)


# ---- 排班 ----

@medical_bp.route("/schedules", methods=["GET"])
@login_required
def list_schedules():
    user = current_user()
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)

    if user["role"] in ("doctor", "nurse"):
        result = medical_service.list_schedules(user["user_id"], page, size)
    else:
        staff_id = request.args.get("staff_id", type=int)
        result = medical_service.list_schedules(staff_id, page, size)

    return jsonify(result)


@medical_bp.route("/schedules", methods=["POST"])
@role_required("doctor", "admin")
def create_schedule():
    data = request.get_json(silent=True) or {}
    if not data.get("staff_id") or not data.get("work_date") or not data.get("shift"):
        return jsonify({"error": "人员、日期和班次不能为空"}), 400
    result = medical_service.create_schedule(data)
    return jsonify(result)
