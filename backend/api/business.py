"""业务接口：患者档案 / 医护工作台 / 排班 / 系统管理。"""
from flask import Blueprint, request

import config as cfg
from models import db
from api.common import ok, fail, token_required, role_required, current_user

business_bp = Blueprint("business", __name__, url_prefix="/api")

# ---------------- 患者 ----------------
@business_bp.route("/patient/hospitalizations", methods=["GET"])
@token_required
def patient_hosp():
    u = current_user()
    rows = db.query("SELECT * FROM hospitalizations WHERE patient_id=%s ORDER BY admit_date DESC", (u["id"],))
    return ok(rows)


@business_bp.route("/patient/bills", methods=["GET"])
@token_required
def patient_bills():
    u = current_user()
    rows = db.query("SELECT * FROM bills WHERE patient_id=%s ORDER BY created_at DESC", (u["id"],))
    return ok(rows)


@business_bp.route("/patient/appointments", methods=["GET"])
@token_required
def patient_appts():
    u = current_user()
    rows = db.query("SELECT * FROM appointments WHERE patient_id=%s ORDER BY date DESC", (u["id"],))
    return ok(rows)


@business_bp.route("/patient/appointments", methods=["POST"])
@token_required
def patient_appt_create():
    u = current_user()
    b = request.get_json(silent=True) or {}
    fee = float(b.get("fee", 0) or 0)
    aid = db.execute(
        "INSERT INTO appointments (patient_id, doctor_id, department, date, time_slot, symptom, fee, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'booked')",
        (u["id"], b.get("doctor_id"), b.get("department"), b.get("date"),
         b.get("time_slot"), b.get("symptom"), fee),
    )
    return ok({"id": aid})


# ---------------- 医生 ----------------
@business_bp.route("/doctor/patients", methods=["GET"])
@role_required("doctor", "admin", "nurse")
def doctor_patients():
    rows = db.query("SELECT id, username, display_name, role FROM users WHERE role='patient' ORDER BY id LIMIT 200")
    return ok(rows)


@business_bp.route("/doctor/hospitalizations", methods=["GET"])
@role_required("doctor", "admin")
def doctor_hosp():
    rows = db.query("SELECT * FROM hospitalizations ORDER BY admit_date DESC LIMIT 200")
    return ok(rows)


@business_bp.route("/doctor/hospitalization", methods=["POST"])
@role_required("doctor", "admin")
def doctor_hosp_create():
    b = request.get_json(silent=True) or {}
    hid = db.execute(
        "INSERT INTO hospitalizations (patient_id, admit_date, department, ward, bed_no, diagnosis, doctor_id, status, total_cost) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (b.get("patient_id"), b.get("admit_date"), b.get("department"), b.get("ward"),
         b.get("bed_no"), b.get("diagnosis"), b.get("doctor_id"), b.get("status", "in_hospital"),
         float(b.get("total_cost", 0) or 0)),
    )
    return ok({"id": hid})


# ---------------- 护士 ----------------
@business_bp.route("/nurse/records", methods=["GET"])
@role_required("nurse", "doctor", "admin")
def nurse_records():
    rows = db.query("SELECT * FROM nursing_records ORDER BY recorded_at DESC LIMIT 200")
    return ok(rows)


@business_bp.route("/nurse/record", methods=["POST"])
@role_required("nurse", "admin")
def nurse_record_create():
    u = current_user()
    b = request.get_json(silent=True) or {}
    rid = db.execute(
        "INSERT INTO nursing_records (patient_id, nurse_id, record_type, content) VALUES (%s, %s, %s, %s)",
        (b.get("patient_id"), u["id"], b.get("record_type", "daily"), b.get("content", "")),
    )
    return ok({"id": rid})


# ---------------- 排班 ----------------
@business_bp.route("/schedule/list", methods=["GET"])
@token_required
def schedule_list():
    rows = db.query("SELECT * FROM schedules ORDER BY work_date DESC LIMIT 200")
    return ok(rows)


@business_bp.route("/schedule/create", methods=["POST"])
@role_required("doctor", "admin", "nurse")
def schedule_create():
    b = request.get_json(silent=True) or {}
    sid = db.execute(
        "INSERT INTO schedules (staff_id, work_date, shift, department, remark, status) VALUES (%s, %s, %s, %s, %s, %s)",
        (b.get("staff_id"), b.get("work_date"), b.get("shift"), b.get("department"),
         b.get("remark"), b.get("status", "on_duty")),
    )
    return ok({"id": sid})


# ---------------- 管理员 ----------------
@business_bp.route("/admin/users", methods=["GET"])
@role_required("admin")
def admin_users():
    rows = db.query("SELECT id, username, display_name, role, created_at FROM users ORDER BY id")
    return ok(rows)


@business_bp.route("/admin/user", methods=["POST"])
@role_required("admin")
def admin_user_create():
    b = request.get_json(silent=True) or {}
    from services.auth import hash_password
    username = (b.get("username") or "").strip()
    if not username:
        return fail("用户名不能为空")
    exists = db.query_one("SELECT id FROM users WHERE username=%s", (username,))
    if exists:
        return fail("用户名已存在", 409)
    uid = db.execute(
        "INSERT INTO users (username, password_hash, role, display_name) VALUES (%s, %s, %s, %s)",
        (username, hash_password(b.get("password", "demo123")), b.get("role", "patient"), b.get("display_name", username)),
    )
    return ok({"id": uid})


@business_bp.route("/admin/user/<int:uid>", methods=["DELETE"])
@role_required("admin")
def admin_user_delete(uid):
    db.execute("DELETE FROM users WHERE id=%s", (uid,))
    return ok({"deleted": uid})
