"""
人工复核（HITL）路由。

功能：
- 医生 / 管理员查看并审批「待复核」的 AI 回答与知识库文档；
- 管理员查询审计日志（audit_logs）。

权限模型：
- 复核动作仅限 doctor / admin；
- 审计日志查询仅限 admin。
"""
from flask import Blueprint, request, jsonify

from backend.utils.jwt_utils import login_required, current_user, role_required
from backend.utils.db import fetchone, fetchall, execute, DB_TYPE
from backend.services import audit_service

review_bp = Blueprint("review", __name__)

REVIEWER_ROLES = ("doctor", "admin")

# 跨数据库「当前时间」表达式：MySQL 用 NOW()，SQLite 用 datetime('now','localtime')
_NOW_SQL = "NOW()" if DB_TYPE == "mysql" else "datetime('now','localtime')"


def _ph() -> str:
    return "%s" if DB_TYPE == "mysql" else "?"


def _paginate() -> tuple[int, int, int]:
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)
    size = max(1, min(size, 100))
    return page, size, (page - 1) * size


def _note() -> str:
    data = request.get_json(silent=True) or {}
    return (data.get("note") or "").strip()[:500]


# ---------------- AI 回答复核 ----------------

@review_bp.route("/answers", methods=["GET"])
@role_required(*REVIEWER_ROLES)
def list_answers():
    user = current_user()
    status = request.args.get("status", "pending")
    page, size, offset = _paginate()
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
    return jsonify({"total": total, "list": rows, "page": page, "size": size})


def _review_answer(msg_id: int, decision: str):
    user = current_user()
    ph = _ph()
    msg = fetchone(
        f"SELECT * FROM messages WHERE id={ph} AND role='assistant'",
        (msg_id,),
    )
    if not msg:
        return jsonify({"error": "回答不存在"}), 404
    if msg["review_status"] != "pending":
        return jsonify({"error": f"该回答已处于「{msg['review_status']}」状态，无法重复复核"}), 409

    note = _note()
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
    return jsonify({"message": "ok", "review_status": decision})


@review_bp.route("/answers/<int:msg_id>/approve", methods=["POST"])
@role_required(*REVIEWER_ROLES)
def approve_answer(msg_id):
    return _review_answer(msg_id, "approved")


@review_bp.route("/answers/<int:msg_id>/reject", methods=["POST"])
@role_required(*REVIEWER_ROLES)
def reject_answer(msg_id):
    return _review_answer(msg_id, "rejected")


# ---------------- 知识库文档复核 ----------------

@review_bp.route("/documents", methods=["GET"])
@role_required(*REVIEWER_ROLES)
def list_documents():
    user = current_user()
    status = request.args.get("status", "pending")
    page, size, offset = _paginate()
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
    return jsonify({"total": total, "list": rows, "page": page, "size": size})


def _review_document(doc_id: int, decision: str):
    user = current_user()
    ph = _ph()
    doc = fetchone(f"SELECT * FROM documents WHERE id={ph}", (doc_id,))
    if not doc:
        return jsonify({"error": "文档不存在"}), 404
    if doc["review_status"] != "pending":
        return jsonify({"error": f"该文档已处于「{doc['review_status']}」状态，无法重复复核"}), 409

    note = _note()
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
    return jsonify({"message": "ok", "review_status": decision})


@review_bp.route("/documents/<int:doc_id>/approve", methods=["POST"])
@role_required(*REVIEWER_ROLES)
def approve_document(doc_id):
    return _review_document(doc_id, "approved")


@review_bp.route("/documents/<int:doc_id>/reject", methods=["POST"])
@role_required(*REVIEWER_ROLES)
def reject_document(doc_id):
    return _review_document(doc_id, "rejected")


# ---------------- 审计日志查询（管理员） ----------------

@review_bp.route("/audit", methods=["GET"])
@role_required("admin")
def audit_logs():
    user = current_user()
    action = request.args.get("action", "")
    target_type = request.args.get("target_type", "")
    page, size, offset = _paginate()
    result = audit_service.list_audit(
        action=action or None,
        target_type=target_type or None,
        page=page,
        size=size,
    )
    return jsonify(result)
