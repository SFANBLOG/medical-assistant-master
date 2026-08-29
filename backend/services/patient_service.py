"""患者个人健康档案服务：最近住院信息、消费明细、预约挂号。"""
from models.db import get_conn
from utils.errors import ApiError


def list_hospitalizations(user_id: int, limit: int = 30) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT h.*, u.display_name AS doctor_name
           FROM hospitalizations h
           LEFT JOIN users u ON u.id = h.doctor_id
           WHERE h.patient_id = ?
           ORDER BY h.admit_date DESC, h.id DESC
           LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def list_bills(user_id: int, category: str = "", status: str = "", limit: int = 200) -> list[dict]:
    conn = get_conn()
    where, params = ["b.patient_id = ?"], [user_id]
    if category:
        where.append("b.category = ?")
        params.append(category)
    if status:
        where.append("b.status = ?")
        params.append(status)
    rows = conn.execute(
        f"""SELECT b.* FROM bills b
            WHERE {' AND '.join(where)}
            ORDER BY b.created_at DESC, b.id DESC
            LIMIT ?""",
        params + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def list_appointments(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT a.*, u.display_name AS doctor_name
           FROM appointments a
           LEFT JOIN users u ON u.id = a.doctor_id
           WHERE a.patient_id = ?
           ORDER BY a.date DESC, a.id DESC""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_appointment(appt_id: int) -> dict:
    conn = get_conn()
    row = conn.execute(
        """SELECT a.*, u.display_name AS doctor_name
           FROM appointments a
           LEFT JOIN users u ON u.id = a.doctor_id
           WHERE a.id = ?""",
        (appt_id,),
    ).fetchone()
    if not row:
        raise ApiError("预约不存在", 404)
    return dict(row)


def create_appointment(
    user_id: int,
    department: str,
    date: str,
    time_slot: str,
    doctor_id: int | None = None,
    symptom: str = "",
) -> dict:
    department = (department or "").strip()
    date = (date or "").strip()
    time_slot = (time_slot or "").strip()
    if not department or not date or not time_slot:
        raise ApiError("科室、就诊日期和时段不能为空", 400)
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO appointments (patient_id, doctor_id, department, date, time_slot, symptom, status, fee)
           VALUES (?,?,?,?,?,?,'booked',20)""",
        (user_id, doctor_id, department, date, time_slot, symptom),
    )
    conn.commit()
    return get_appointment(cur.lastrowid)


def cancel_appointment(user_id: int, appt_id: int) -> None:
    conn = get_conn()
    cur = conn.execute(
        "UPDATE appointments SET status='cancelled' WHERE id=? AND patient_id=?",
        (appt_id, user_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        raise ApiError("预约不存在或无权操作", 404)
