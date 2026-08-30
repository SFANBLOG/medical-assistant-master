"""Agent 路由：SSE 流式问答 + 工具清单。"""
import json

from flask import Blueprint, request, jsonify, Response, stream_with_context

from backend.utils.jwt_utils import login_required, current_user
from backend.utils.db import fetchone
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
