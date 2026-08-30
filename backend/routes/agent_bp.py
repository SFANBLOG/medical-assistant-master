"""Agent 路由：SSE 流式问答 + 工具清单。"""
import json

from flask import Blueprint, request, jsonify, Response, stream_with_context

from backend.utils.jwt_utils import login_required, current_user
from backend.utils.db import fetchone, fetchall
from backend.agent import service as agent_service
from backend.agent import tools as toolmod

agent_bp = Blueprint("agent", __name__)


@agent_bp.route("/tools", methods=["GET"])
@login_required
def list_tools():
    """列出 Agent 当前可用的工具（供前端展示/调试）。"""
    return jsonify([
        {"name": t.name, "description": t.description, "parameters": t.parameters}
        for t in toolmod.TOOLS
    ])


@agent_bp.route("/stream/<conv_id>", methods=["POST"])
@login_required
def agent_stream(conv_id):
    """
    Agent 模式 SSE 流式问答。

    请求体: {"question": "...", "kb_id": null}
    响应: SSE 流（thought / tool_call / observation / citations / message / done / error）
    """
    user = current_user()
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    kb_id = data.get("kb_id")

    if not question:
        return jsonify({"error": "问题不能为空"}), 400

    # 校验会话归属
    conv = fetchone(
        "SELECT id FROM conversations WHERE id = %s AND user_id = %s",
        (conv_id, user["user_id"]),
    )
    if not conv:
        return jsonify({"error": "会话不存在或无权限"}), 404

    def generate():
        yield from agent_service.agent_stream_sse(
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


@agent_bp.route("/trace/<int:message_id>", methods=["GET"])
@login_required
def get_trace(message_id):
    """查询某条 AI 消息的 Agent 推理轨迹与引用来源（可观测 / 审计 / 评测）。"""
    user = current_user()
    row = fetchone(
        "SELECT m.id, m.conversation_id, m.content, m.agent_steps, m.review_status "
        "FROM messages m JOIN conversations c ON m.conversation_id = c.id "
        "WHERE m.id = %s AND c.user_id = %s AND m.role = 'assistant'",
        (message_id, user["user_id"]),
    )
    if not row:
        return jsonify({"error": "消息不存在或无权限"}), 404

    raw = row.get("agent_steps") or "[]"
    try:
        steps = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        steps = []

    cites = fetchall(
        "SELECT document_id, chunk_index, source_text, title, similarity "
        "FROM citations WHERE message_id = %s",
        (message_id,),
    )

    return jsonify({
        "message_id": message_id,
        "conversation_id": row.get("conversation_id"),
        "review_status": row.get("review_status"),
        "answer": row.get("content"),
        "agent_steps": steps,
        "citations": cites,
    })
