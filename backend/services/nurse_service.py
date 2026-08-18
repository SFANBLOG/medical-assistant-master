"""护士工作台服务：患者信息、护理记录。"""
from models.db import get_conn
from utils.errors import ApiError


def list_patients(q: str = "", limit: int = 100) -> list[dict]:
    conn = get_conn()
    where, params = ["u.role = 'patient'"], []
    if q:
        where.append("(u.username LIKE ? OR u.display_name LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    rows = conn.execute(
        f"""SELECT u.id, u.username, u.display_name,
                   (SELECT h.status FROM hospitalizations h
                     WHERE h.patient_id = u.id ORDER BY h.admit_date DESC LIMIT 1) AS current_status,
                   (SELECT h.department FROM hospitalizations h
                     WHERE h.patient_id = u.id ORDER BY h.admit_date DESC LIMIT 1) AS current_department,
                   (SELECT h.bed_no FROM hospitalizations h
                     WHERE h.patient_id = u.id ORDER BY h.admit_date DESC LIMIT 1) AS current_bed
            FROM users u
            WHERE {' AND '.join(where)}
            ORDER BY u.id
            LIMIT ?""",
        params + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def list_nursing_records(patient_id: int = 0, limit: int = 200) -> list[dict]:
    conn = get_conn()
    where, params = ["1=1"], []
    if patient_id:
        where.append("n.patient_id = ?")
        params.append(patient_id)
    rows = conn.execute(
        f"""SELECT n.*, p.display_name AS patient_name, u.display_name AS nurse_name
            FROM nursing_records n
            JOIN users p ON p.id = n.patient_id
            LEFT JOIN users u ON u.id = n.nurse_id
            WHERE {' AND '.join(where)}
            ORDER BY n.recorded_at DESC, n.id DESC
            LIMIT ?""",
        params + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def create_nursing_record(
    nurse_id: int,
    patient_id: int,
    content: str,
    record_type: str = "daily",
    recorded_at: str = "",
) -> dict:
    content = (content or "").strip()
    if not content:
        raise ApiError("护理记录内容不能为空", 400)
    if record_type not in ("daily", "medication", "vitals", "other"):
        record_type = "daily"
    if not recorded_at:
        from datetime import datetime

        recorded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO nursing_records (patient_id, nurse_id, content, record_type, recorded_at) "
        "VALUES (?,?,?,?,?)",
        (patient_id, nurse_id, content, record_type, recorded_at),
    )
    conn.commit()
    row = conn.execute(
        """SELECT n.*, p.display_name AS patient_name, u.display_name AS nurse_name
           FROM nursing_records n
           JOIN users p ON p.id = n.patient_id
           LEFT JOIN users u ON u.id = n.nurse_id
           WHERE n.id = ?""",
        (cur.lastrowid,),
    ).fetchone()
    return dict(row)
