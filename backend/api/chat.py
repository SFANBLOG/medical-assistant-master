"""智能咨询接口（SSE 流式）与咨询历史。"""
from flask import Blueprint, Response, request, stream_with_context

from models import db
from services import rag as rag_svc
from api.common import ok, fail, token_required, current_user

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@chat_bp.route("/consult", methods=["POST"])
@token_required
def consult():
    u = current_user()
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    kb_id = body.get("kb_id")
    if not question:
        return fail("问题不能为空")

    def gen():
        yield from rag_svc.answer(u["id"], u["role"], question, kb_id=int(kb_id) if kb_id else None)

    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@chat_bp.route("/history", methods=["GET"])
@token_required
def history():
    u = current_user()
    rows = db.query(
        "SELECT * FROM conversations WHERE user_id=%s ORDER BY updated_at DESC LIMIT 50",
        (u["id"],),
    )
    return ok(rows)


@chat_bp.route("/conversation/<cid>", methods=["GET"])
@token_required
def conversation(cid):
    u = current_user()
    conv = db.query_one("SELECT * FROM conversations WHERE id=%s AND user_id=%s", (cid, u["id"]))
    if not conv:
        return fail("会话不存在", 404)
    msgs = db.query("SELECT * FROM messages WHERE conversation_id=%s ORDER BY id", (cid,))
    return ok({"conversation": conv, "messages": msgs})
