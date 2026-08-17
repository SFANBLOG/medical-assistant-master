"""医护排班服务（医生/护士共用）。"""
from models.db import get_conn
from utils.errors import ApiError


def list_schedules(staff_id: int = 0, department: str = "", limit: int = 200) -> list[dict]:
    conn = get_conn()
    where, params = ["1=1"], []
    if staff_id:
        where.append("s.staff_id = ?")
        params.append(staff_id)
    if department:
        where.append("s.department LIKE ?")
        params.append(f"%{department}%")
    rows = conn.execute(
        f"""SELECT s.*, u.display_name AS staff_name, u.role AS staff_role
            FROM schedules s
            JOIN users u ON u.id = s.staff_id
            WHERE {' AND '.join(where)}
            ORDER BY s.work_date DESC, s.id DESC
            LIMIT ?""",
        params + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def create_schedule(
    staff_id: int,
    work_date: str,
    shift: str = "day",
    department: str = "",
    remark: str = "",
) -> dict:
    work_date = (work_date or "").strip()
    if not work_date:
        raise ApiError("排班日期不能为空", 400)
    if shift not in ("day", "night", "evening", "off"):
        shift = "day"
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO schedules (staff_id, work_date, shift, department, remark, status)
           VALUES (?,?,?,?,?,'on_duty')""",
        (staff_id, work_date, shift, department.strip(), remark.strip()),
    )
    conn.commit()
    row = conn.execute(
        """SELECT s.*, u.display_name AS staff_name, u.role AS staff_role
           FROM schedules s JOIN users u ON u.id = s.staff_id WHERE s.id = ?""",
        (cur.lastrowid,),
    ).fetchone()
    return dict(row)
