"""
医疗业务服务：住院信息、消费明细、预约挂号、护理记录、排班。
"""
from backend.utils.db import fetchone, fetchall, execute


# ---- 住院信息 ----

def list_hospitalizations(patient_id: int = None, page: int = 1, size: int = 20) -> dict:
    """获取住院信息列表。"""
    offset = (page - 1) * size
    if patient_id:
        total = fetchone("SELECT COUNT(*) AS cnt FROM hospitalizations WHERE patient_id = %s", (patient_id,))["cnt"]
        rows = fetchall(
            "SELECT h.*, u.display_name AS patient_name, d.display_name AS doctor_name "
            "FROM hospitalizations h "
            "LEFT JOIN users u ON h.patient_id = u.id "
            "LEFT JOIN users d ON h.doctor_id = d.id "
            "WHERE h.patient_id = %s ORDER BY h.id DESC LIMIT %s OFFSET %s",
            (patient_id, size, offset)
        )
    else:
        total = fetchone("SELECT COUNT(*) AS cnt FROM hospitalizations")["cnt"]
        rows = fetchall(
            "SELECT h.*, u.display_name AS patient_name, d.display_name AS doctor_name "
            "FROM hospitalizations h "
            "LEFT JOIN users u ON h.patient_id = u.id "
            "LEFT JOIN users d ON h.doctor_id = d.id "
            "ORDER BY h.id DESC LIMIT %s OFFSET %s",
            (size, offset)
        )
    return {"total": total, "list": rows, "page": page, "size": size}


def create_hospitalization(data: dict) -> dict:
    """创建住院记录。"""
    execute(
        "INSERT INTO hospitalizations (patient_id, admit_date, discharge_date, department, ward, "
        "bed_no, diagnosis, doctor_id, status, total_cost) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (data.get("patient_id"), data.get("admit_date"), data.get("discharge_date"),
         data.get("department"), data.get("ward"), data.get("bed_no"),
         data.get("diagnosis"), data.get("doctor_id"),
         data.get("status", "in_hospital"), data.get("total_cost", 0))
    )
    row = fetchone("SELECT * FROM hospitalizations ORDER BY id DESC LIMIT 1")
    return row


def update_hospitalization(hosp_id: int, data: dict) -> dict:
    """更新住院记录。"""
    fields = []
    values = []
    for k in ["admit_date", "discharge_date", "department", "ward", "bed_no",
              "diagnosis", "doctor_id", "status", "total_cost"]:
        if k in data and data[k] is not None:
            fields.append(f"{k} = %s")
            values.append(data[k])
    if not fields:
        return fetchone("SELECT * FROM hospitalizations WHERE id = %s", (hosp_id,))
    values.append(hosp_id)
    execute(f"UPDATE hospitalizations SET {', '.join(fields)} WHERE id = %s", values)
    return fetchone("SELECT * FROM hospitalizations WHERE id = %s", (hosp_id,))


# ---- 消费明细 ----

def list_bills(patient_id: int = None, page: int = 1, size: int = 20) -> dict:
    """获取消费明细列表。"""
    offset = (page - 1) * size
    if patient_id:
        total = fetchone("SELECT COUNT(*) AS cnt FROM bills WHERE patient_id = %s", (patient_id,))["cnt"]
        rows = fetchall(
            "SELECT b.*, u.display_name AS patient_name FROM bills b "
            "LEFT JOIN users u ON b.patient_id = u.id "
            "WHERE b.patient_id = %s ORDER BY b.id DESC LIMIT %s OFFSET %s",
            (patient_id, size, offset)
        )
    else:
        total = fetchone("SELECT COUNT(*) AS cnt FROM bills")["cnt"]
        rows = fetchall(
            "SELECT b.*, u.display_name AS patient_name FROM bills b "
            "LEFT JOIN users u ON b.patient_id = u.id "
            "ORDER BY b.id DESC LIMIT %s OFFSET %s",
            (size, offset)
        )
    return {"total": total, "list": rows, "page": page, "size": size}


# ---- 预约挂号 ----

def list_appointments(patient_id: int = None, role: str = None, page: int = 1, size: int = 20) -> dict:
    """获取预约挂号列表。"""
    offset = (page - 1) * size
    if patient_id:
        total = fetchone("SELECT COUNT(*) AS cnt FROM appointments WHERE patient_id = %s", (patient_id,))["cnt"]
        rows = fetchall(
            "SELECT a.*, u.display_name AS patient_name, d.display_name AS doctor_name "
            "FROM appointments a "
            "LEFT JOIN users u ON a.patient_id = u.id "
            "LEFT JOIN users d ON a.doctor_id = d.id "
            "WHERE a.patient_id = %s ORDER BY a.id DESC LIMIT %s OFFSET %s",
            (patient_id, size, offset)
        )
    else:
        total = fetchone("SELECT COUNT(*) AS cnt FROM appointments")["cnt"]
        rows = fetchall(
            "SELECT a.*, u.display_name AS patient_name, d.display_name AS doctor_name "
            "FROM appointments a "
            "LEFT JOIN users u ON a.patient_id = u.id "
            "LEFT JOIN users d ON a.doctor_id = d.id "
            "ORDER BY a.id DESC LIMIT %s OFFSET %s",
            (size, offset)
        )
    return {"total": total, "list": rows, "page": page, "size": size}


def create_appointment(data: dict) -> dict:
    """创建预约挂号。"""
    execute(
        "INSERT INTO appointments (patient_id, doctor_id, department, date, time_slot, symptom, fee, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (data.get("patient_id"), data.get("doctor_id"), data.get("department"),
         data.get("date"), data.get("time_slot"), data.get("symptom"),
         data.get("fee", 0), data.get("status", "booked"))
    )
    return fetchone("SELECT * FROM appointments ORDER BY id DESC LIMIT 1")


def update_appointment(appt_id: int, data: dict) -> dict:
    """更新预约状态。"""
    fields = []
    values = []
    for k in ["status", "date", "time_slot", "doctor_id", "department", "symptom", "fee"]:
        if k in data and data[k] is not None:
            fields.append(f"{k} = %s")
            values.append(data[k])
    if not fields:
        return fetchone("SELECT * FROM appointments WHERE id = %s", (appt_id,))
    values.append(appt_id)
    execute(f"UPDATE appointments SET {', '.join(fields)} WHERE id = %s", values)
    return fetchone("SELECT * FROM appointments WHERE id = %s", (appt_id,))


# ---- 护理记录 ----

def list_nursing_records(patient_id: int = None, page: int = 1, size: int = 20) -> dict:
    """获取护理记录列表。"""
    offset = (page - 1) * size
    if patient_id:
        total = fetchone("SELECT COUNT(*) AS cnt FROM nursing_records WHERE patient_id = %s", (patient_id,))["cnt"]
        rows = fetchall(
            "SELECT n.*, u.display_name AS patient_name, nu.display_name AS nurse_name "
            "FROM nursing_records n "
            "LEFT JOIN users u ON n.patient_id = u.id "
            "LEFT JOIN users nu ON n.nurse_id = nu.id "
            "WHERE n.patient_id = %s ORDER BY n.id DESC LIMIT %s OFFSET %s",
            (patient_id, size, offset)
        )
    else:
        total = fetchone("SELECT COUNT(*) AS cnt FROM nursing_records")["cnt"]
        rows = fetchall(
            "SELECT n.*, u.display_name AS patient_name, nu.display_name AS nurse_name "
            "FROM nursing_records n "
            "LEFT JOIN users u ON n.patient_id = u.id "
            "LEFT JOIN users nu ON n.nurse_id = nu.id "
            "ORDER BY n.id DESC LIMIT %s OFFSET %s",
            (size, offset)
        )
    return {"total": total, "list": rows, "page": page, "size": size}


def create_nursing_record(data: dict) -> dict:
    """创建护理记录。"""
    execute(
        "INSERT INTO nursing_records (patient_id, nurse_id, record_type, content) "
        "VALUES (%s, %s, %s, %s)",
        (data.get("patient_id"), data.get("nurse_id"),
         data.get("record_type", "daily"), data.get("content"))
    )
    return fetchone("SELECT * FROM nursing_records ORDER BY id DESC LIMIT 1")


# ---- 排班 ----

def list_schedules(staff_id: int = None, page: int = 1, size: int = 20) -> dict:
    """获取排班列表。"""
    offset = (page - 1) * size
    if staff_id:
        total = fetchone("SELECT COUNT(*) AS cnt FROM schedules WHERE staff_id = %s", (staff_id,))["cnt"]
        rows = fetchall(
            "SELECT s.*, u.display_name AS staff_name, u.role AS staff_role "
            "FROM schedules s LEFT JOIN users u ON s.staff_id = u.id "
            "WHERE s.staff_id = %s ORDER BY s.work_date DESC LIMIT %s OFFSET %s",
            (staff_id, size, offset)
        )
    else:
        total = fetchone("SELECT COUNT(*) AS cnt FROM schedules")["cnt"]
        rows = fetchall(
            "SELECT s.*, u.display_name AS staff_name, u.role AS staff_role "
            "FROM schedules s LEFT JOIN users u ON s.staff_id = u.id "
            "ORDER BY s.work_date DESC LIMIT %s OFFSET %s",
            (size, offset)
        )
    return {"total": total, "list": rows, "page": page, "size": size}


def create_schedule(data: dict) -> dict:
    """创建排班。"""
    execute(
        "INSERT INTO schedules (staff_id, work_date, shift, department, remark, status) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (data.get("staff_id"), data.get("work_date"), data.get("shift"),
         data.get("department"), data.get("remark", ""), data.get("status", "on_duty"))
    )
    return fetchone("SELECT * FROM schedules ORDER BY id DESC LIMIT 1")
