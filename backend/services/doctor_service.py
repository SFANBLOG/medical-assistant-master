"""医生工作台服务：患者管理、住院信息管理。"""
from models.db import get_conn
from utils.errors import ApiError


def list_patients(q: str = "", page: int = 1, page_size: int = 10) -> dict:
    conn = get_conn()
    where, params = ["role = 'patient'"], []
    if q:
        where.append("(username LIKE ? OR display_name LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    total = conn.execute(
        f"SELECT COUNT(*) FROM users WHERE {' AND '.join(where)}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"""SELECT id, username, role, display_name, created_at FROM users
            WHERE {' AND '.join(where)}
            ORDER BY id LIMIT ? OFFSET ?""",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        h = conn.execute(
            """SELECT id, department, diagnosis, status, admit_date
               FROM hospitalizations WHERE patient_id=?
               ORDER BY admit_date DESC LIMIT 1""",
            (r["id"],),
        ).fetchone()
        item["latest_admission"] = dict(h) if h else None
        items.append(item)
    return {"total": total, "items": items}


def list_patient_hospitalizations(patient_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT h.*, u.display_name AS doctor_name
           FROM hospitalizations h
           LEFT JOIN users u ON u.id = h.doctor_id
           WHERE h.patient_id = ?
           ORDER BY h.admit_date DESC, h.id DESC""",
        (patient_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_all_hospitalizations(status: str = "", q: str = "", limit: int = 200) -> list[dict]:
    conn = get_conn()
    where, params = ["1=1"], []
    if status:
        where.append("h.status = ?")
        params.append(status)
    if q:
        where.append("(p.username LIKE ? OR p.display_name LIKE ? OR h.diagnosis LIKE ?)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    rows = conn.execute(
        f"""SELECT h.*, p.display_name AS patient_name, p.username AS patient_username,
                   u.display_name AS doctor_name
            FROM hospitalizations h
            JOIN users p ON p.id = h.patient_id
            LEFT JOIN users u ON u.id = h.doctor_id
            WHERE {' AND '.join(where)}
            ORDER BY h.admit_date DESC, h.id DESC
            LIMIT ?""",
        params + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def create_hospitalization(
    patient_id: int,
    department: str,
    admit_date: str,
    diagnosis: str = "",
    ward: str = "",
    bed_no: str = "",
    doctor_id: int | None = None,
) -> dict:
    conn = get_conn()
    if not department.strip() or not admit_date.strip():
        raise ApiError("科室和入院日期不能为空", 400)
    cur = conn.execute(
        """INSERT INTO hospitalizations (patient_id, admit_date, department, ward, bed_no, diagnosis, doctor_id, status, total_cost)
           VALUES (?,?,?,?,?,?,?,'in_hospital',0)""",
        (patient_id, admit_date.strip(), department.strip(), ward.strip(), bed_no.strip(),
         diagnosis.strip(), doctor_id),
    )
    conn.commit()
    return _get_hospitalization(cur.lastrowid)


def _get_hospitalization(hid: int) -> dict:
    conn = get_conn()
    row = conn.execute(
        """SELECT h.*, p.display_name AS patient_name, u.display_name AS doctor_name
           FROM hospitalizations h
           JOIN users p ON p.id = h.patient_id
           LEFT JOIN users u ON u.id = h.doctor_id
           WHERE h.id = ?""",
        (hid,),
    ).fetchone()
    if not row:
        raise ApiError("住院记录不存在", 404)
    return dict(row)


def update_hospitalization(
    hid: int,
    status: str = "",
    discharge_date: str = "",
    diagnosis: str = "",
    total_cost: float | None = None,
) -> dict:
    conn = get_conn()
    h = _get_hospitalization(hid)
    new_status = status or h["status"]
    if new_status not in ("in_hospital", "discharged"):
        raise ApiError("无效的住院状态", 400)
    sets, params = ["status = ?"], [new_status]
    if discharge_date:
        sets.append("discharge_date = ?")
        params.append(discharge_date)
    if diagnosis:
        sets.append("diagnosis = ?")
        params.append(diagnosis)
    if total_cost is not None:
        sets.append("total_cost = ?")
        params.append(total_cost)
    params.append(hid)
    conn.execute(f"UPDATE hospitalizations SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    return _get_hospitalization(hid)
