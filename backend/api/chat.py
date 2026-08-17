from flask import Blueprint, g, request

from api.decorators import require_auth
from services import chat_service
from utils.errors import ApiError

chat_bp = Blueprint("chat", __name__)


@chat_bp.post("/ask")
@require_auth
def ask():
    data = request.get_json(silent=True) or {}
    kb_id = data.get("kb_id")
    question = data.get("question", "")
    if not kb_id:
        raise ApiError("请选择知识库", 400)
    return chat_service.ask(
        g.user,
        conversation_id=data.get("conversation_id"),
        kb_id=int(kb_id),
        question=question,
    )


@chat_bp.get("/conversations")
@require_auth
def list_conversations():
    q = request.args.get("q", "")
    page = max(int(request.args.get("page", "1")), 1)
    page_size = min(max(int(request.args.get("page_size", "10")), 1), 50)
    return chat_service.list_conversations(g.user["id"], q, page, page_size)


@chat_bp.get("/conversations/<conversation_id>")
@require_auth
def get_conversation(conversation_id: str):
    return chat_service.get_conversation(g.user["id"], conversation_id)


@chat_bp.delete("/conversations/<conversation_id>")
@require_auth
def delete_conversation(conversation_id: str):
    chat_service.delete_conversation(g.user["id"], conversation_id)
    return {"ok": True}
