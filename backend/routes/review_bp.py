"""
人工复核（HITL）路由（FastAPI APIRouter）。

功能：
- 医生 / 管理员查看并审批「待复核」的 AI 回答与知识库文档；
- 医生 / 管理员审批「预约请求」（写操作 HITL：审核通过后才真正建单）；
- 管理员查询审计日志（audit_logs）。

权限模型：
- 复核动作仅限 doctor / admin；
- 审计日志查询仅限 admin。
"""
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from backend.services import audit_service
from backend.utils.api_utils import json_body
from backend.utils.db import fetchone, fetchall, execute, DB_TYPE, NOW_SQL
from backend.utils.jwt_utils import get_current_user, require_roles

router = APIRouter()

REVIEWER_ROLES = ("doctor", "admin")

# 跨数据库「当前时间」表达式：统一取自 backend.utils.db.NOW_SQL
# （MySQL 用 NOW()，SQLite 用 datetime('now','localtime')）
_NOW_SQL = NOW_SQL

_review_dep = require_roles(*REVIEWER_ROLES)


def _ph() -> str:
    return "%s" if DB_TYPE == "mysql" else "?"


def _norm_size(size: int) -> int:
    return max(1, min(size, 100))


def _note_from(data: dict) -> str:
    return (data.get("note") or "").strip()[:500]


# ---------------- AI 回答复核 ----------------

@router.get("/answers")
def list_answers(user: dict = Depends(_review_dep),
                 status: str = Query("pending"),
                 page: int = Query(1), size: int = Query(20)):
    size = _norm_size(size)
    offset = (page - 1) * size
    ph = _ph()
    total = fetchone(
        f"SELECT COUNT(*) AS cnt FROM messages WHERE role='assistant' AND review_status={ph}",
        (status,),
    )["cnt"]
    rows = fetchall(
        f"""SELECT m.id, m.conversation_id, m.content, m.review_status, m.reviewer_id,
                  m.reviewed_at, m.review_note, m.created_at,
                  c.user_id, c.title AS conv_title,
                  u.username AS asker_username, u.display_name AS asker_name
           FROM messages m
           JOIN conversations c ON m.conversation_id = c.id
           LEFT JOIN users u ON c.user_id = u.id
           WHERE m.role='assistant' AND m.review_status={ph}
           ORDER BY m.id DESC LIMIT {ph} OFFSET {ph}""",
        (status, size, offset),
    )
    return {"total": total, "list": rows, "page": page, "size": size}


def _review_answer(msg_id: int, decision: str, user: dict, note: str):
    ph = _ph()
    msg = fetchone(
        f"SELECT * FROM messages WHERE id={ph} AND role='assistant'",
        (msg_id,),
    )
    if not msg:
        return JSONResponse({"error": "回答不存在"}, status_code=404)
    if msg["review_status"] != "pending":
        return JSONResponse({"error": f"该回答已处于「{msg['review_status']}」状态，无法重复复核"}, status_code=409)

    execute(
        f"UPDATE messages SET review_status={ph}, reviewer_id={ph}, reviewed_at={_NOW_SQL}, review_note={ph} "
        f"WHERE id={ph}",
        (decision, user["user_id"], note, msg_id),
    )
    audit_service.write_audit(
        actor_id=user["user_id"],
        actor_role=user["role"],
        action=f"ai_answer_{decision}",
        target_type="message",
        target_id=msg_id,
        detail=note or f"AI 回答（会话 {msg['conversation_id']}）已{('通过' if decision=='approved' else '驳回')}",
    )
    return {"message": "ok", "review_status": decision}


@router.post("/answers/{msg_id}/approve")
def approve_answer(msg_id: int, user: dict = Depends(_review_dep),
                   data: dict = Depends(json_body)):
    return _review_answer(msg_id, "approved", user, _note_from(data))


@router.post("/answers/{msg_id}/reject")
def reject_answer(msg_id: int, user: dict = Depends(_review_dep),
                  data: dict = Depends(json_body)):
    return _review_answer(msg_id, "rejected", user, _note_from(data))


# ---------------- 知识库文档复核 ----------------

@router.get("/documents")
def list_documents(user: dict = Depends(_review_dep),
                   status: str = Query("pending"),
                   page: int = Query(1), size: int = Query(20)):
    size = _norm_size(size)
    offset = (page - 1) * size
    ph = _ph()
    total = fetchone(
        f"SELECT COUNT(*) AS cnt FROM documents WHERE review_status={ph}",
        (status,),
    )["cnt"]
    rows = fetchall(
        f"""SELECT d.id, d.kb_id, d.filename, d.visibility, d.status, d.review_status,
                  d.reviewer_id, d.reviewed_at, d.review_note, d.created_at,
                  k.name AS kb_name
           FROM documents d
           LEFT JOIN knowledge_bases k ON d.kb_id = k.id
           WHERE d.review_status={ph}
           ORDER BY d.id DESC LIMIT {ph} OFFSET {ph}""",
        (status, size, offset),
    )
    return {"total": total, "list": rows, "page": page, "size": size}


def _review_document(doc_id: int, decision: str, user: dict, note: str):
    ph = _ph()
    doc = fetchone(f"SELECT * FROM documents WHERE id={ph}", (doc_id,))
    if not doc:
        return JSONResponse({"error": "文档不存在"}, status_code=404)
    if doc["review_status"] != "pending":
        return JSONResponse({"error": f"该文档已处于「{doc['review_status']}」状态，无法重复复核"}, status_code=409)

    execute(
        f"UPDATE documents SET review_status={ph}, reviewer_id={ph}, reviewed_at={_NOW_SQL}, review_note={ph} "
        f"WHERE id={ph}",
        (decision, user["user_id"], note, doc_id),
    )
    audit_service.write_audit(
        actor_id=user["user_id"],
        actor_role=user["role"],
        action=f"doc_{decision}",
        target_type="document",
        target_id=doc_id,
        detail=note or f"文档《{doc['filename']}》已{('通过' if decision=='approved' else '驳回')}",
    )
    return {"message": "ok", "review_status": decision}


@router.post("/documents/{doc_id}/approve")
def approve_document(doc_id: int, user: dict = Depends(_review_dep),
                     data: dict = Depends(json_body)):
    return _review_document(doc_id, "approved", user, _note_from(data))


@router.post("/documents/{doc_id}/reject")
def reject_document(doc_id: int, user: dict = Depends(_review_dep),
                    data: dict = Depends(json_body)):
    return _review_document(doc_id, "rejected", user, _note_from(data))


# ---------------- 预约请求复核（写操作 HITL） ----------------

@router.get("/appointments")
def list_appointment_requests(user: dict = Depends(_review_dep),
                              status: str = Query("pending"),
                              page: int = Query(1), size: int = Query(20)):
    size = _norm_size(size)
    offset = (page - 1) * size
    ph = _ph()
    total = fetchone(
        f"SELECT COUNT(*) AS cnt FROM appointment_requests WHERE review_status={ph}",
        (status,),
    )["cnt"]
    rows = fetchall(
        f"""SELECT r.id, r.user_id, r.request_json, r.review_status, r.reviewer_id,
                  r.reviewed_at, r.review_note, r.created_at, r.conversation_id,
                  u.username AS patient_username, u.display_name AS patient_name
           FROM appointment_requests r
           LEFT JOIN users u ON r.user_id = u.id
           WHERE r.review_status={ph}
           ORDER BY r.id DESC LIMIT {ph} OFFSET {ph}""",
        (status, size, offset),
    )
    out = []
    for r in rows:
        try:
            req = json.loads(r["request_json"]) if isinstance(r.get("request_json"), str) else r.get("request_json")
        except (ValueError, TypeError):
            req = {}
        item = dict(r)
        item["request"] = req
        out.append(item)
    return {"total": total, "list": out, "page": page, "size": size}


def _review_appointment_request(req_id: int, decision: str, user: dict, note: str):
    ph = _ph()
    req = fetchone(f"SELECT * FROM appointment_requests WHERE id={ph}", (req_id,))
    if not req:
        return JSONResponse({"error": "预约请求不存在"}, status_code=404)
    if req["review_status"] != "pending":
        return JSONResponse({"error": f"该请求已处于「{req['review_status']}」状态，无法重复复核"}, status_code=409)

    new_appt_id = None
    if decision == "approved":
        try:
            payload = json.loads(req["request_json"]) if isinstance(req["request_json"], str) else req["request_json"]
        except (ValueError, TypeError):
            payload = {}
        execute(
            "INSERT INTO appointments (patient_id, doctor_id, department, date, time_slot, symptom, status, fee) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'booked', 20)",
            (
                payload.get("patient_id"),
                payload.get("doctor_id"),
                payload.get("department"),
                payload.get("date"),
                payload.get("time_slot"),
                payload.get("symptom", ""),
            ),
        )
        row = fetchone(
            "SELECT id FROM appointments WHERE patient_id=%s ORDER BY id DESC LIMIT 1",
            (payload.get("patient_id"),),
        )
        new_appt_id = row["id"] if row else None

    execute(
        f"UPDATE appointment_requests SET review_status={ph}, reviewer_id={ph}, reviewed_at={_NOW_SQL}, review_note={ph} "
        f"WHERE id={ph}",
        (decision, user["user_id"], note, req_id),
    )
    audit_service.write_audit(
        actor_id=user["user_id"],
        actor_role=user["role"],
        action=f"appointment_request_{decision}",
        target_type="appointment_request",
        target_id=req_id,
        detail=note or f"预约请求 #{req_id} 已{('通过并建单' if decision == 'approved' else '驳回')}",
    )
    return {"message": "ok", "review_status": decision, "appointment_id": new_appt_id}


@router.post("/appointments/{req_id}/approve")
def approve_appointment_request(req_id: int, user: dict = Depends(_review_dep),
                                data: dict = Depends(json_body)):
    return _review_appointment_request(req_id, "approved", user, _note_from(data))


@router.post("/appointments/{req_id}/reject")
def reject_appointment_request(req_id: int, user: dict = Depends(_review_dep),
                               data: dict = Depends(json_body)):
    return _review_appointment_request(req_id, "rejected", user, _note_from(data))


# ---------------- 审计日志查询（管理员） ----------------

@router.get("/audit")
def audit_logs(user: dict = Depends(require_roles("admin")),
               action: str = Query(""), target_type: str = Query(""),
               page: int = Query(1), size: int = Query(20)):
    size = _norm_size(size)
    return audit_service.list_audit(
        action=action or None,
        target_type=target_type or None,
        page=page,
        size=size,
    )
