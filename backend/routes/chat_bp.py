"""聊天路由（含 SSE 流式）"""

from flask import Blueprint, request, jsonify, Response, stream_with_context

from backend.services import chat_service
from backend.utils.jwt_utils import login_required, current_user

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/conversations", methods=["GET"])
@login_required
def list_conversations():
    user = current_user()
    rows = chat_service.list_conversations(user["user_id"])
    return jsonify(rows)


@chat_bp.route("/conversations", methods=["POST"])
@login_required
def create_conversation():
    user = current_user()
    data = request.get_json(silent=True) or {}
    result = chat_service.create_conversation(
        user["user_id"],
        kb_id=data.get("kb_id"),
        title=data.get("title", "新对话")
    )
    return jsonify(result)


@chat_bp.route("/conversations/<conv_id>", methods=["GET"])
@login_required
def get_conversation(conv_id):
    user = current_user()
    conv = chat_service.get_conversation(conv_id, user["user_id"])
    if not conv:
        return jsonify({"error": "会话不存在"}), 404
    return jsonify(conv)


@chat_bp.route("/conversations/<conv_id>", methods=["DELETE"])
@login_required
def delete_conversation(conv_id):
    user = current_user()
    ok = chat_service.delete_conversation(conv_id, user["user_id"])
    if not ok:
        return jsonify({"error": "会话不存在或无权限"}), 404
    return jsonify({"message": "已删除"})


@chat_bp.route("/stream/<conv_id>", methods=["POST"])
@login_required
def chat_stream(conv_id):
    """
    SSE 流式问答。

    请求体: {"question": "...", "kb_id": null}
    响应: SSE 流
    """
    user = current_user()
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    kb_id = data.get("kb_id")

    if not question:
        return jsonify({"error": "问题不能为空"}), 400

    # 验证会话归属
    conv = chat_service.get_conversation(conv_id, user["user_id"])
    if not conv:
        return jsonify({"error": "会话不存在"}), 404

    def generate():
        yield from chat_service.chat_stream_sse(
            conv_id=conv_id,
            user_id=user["user_id"],
            role=user["role"],
            question=question,
            kb_id=kb_id,
        )

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@chat_bp.route("/history", methods=["GET"])
@login_required
def chat_history():
    user = current_user()
    limit = request.args.get("limit", 50, type=int)
    rows = chat_service.get_chat_history(user["user_id"], limit)
    return jsonify(rows)
