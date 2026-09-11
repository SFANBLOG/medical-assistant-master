"""
MCP Server 实现。

将项目工具暴露为 MCP（Model Context Protocol）标准接口，
支持外部 AI 系统（如 Claude Desktop、Cursor）通过 MCP 协议调用。

传输层：HTTP JSON-RPC（Flask 蓝图挂载）
协议版本：MCP 2024-11-05
"""
from flask import Blueprint, request

from backend.mcp.resources import list_knowledge_resources, read_knowledge_resource
from backend.mcp.tools_registry import list_all_mcp_tools, call_mcp_tool

mcp_bp = Blueprint("mcp", __name__)

# MCP 服务器能力声明
_SERVER_INFO = {
    "name": "medical-assistant",
    "version": "1.0.0",
    "description": "医智助手 MCP 服务器，提供医学知识库检索、分诊、预约、病历查询等工具。",
    "capabilities": {
        "tools": {"listChanged": False},
        "resources": {"subscribe": False, "listChanged": False},
    },
}


@mcp_bp.route("/mcp", methods=["POST"])
def mcp_endpoint():
    """MCP JSON-RPC 端点。

    接收 JSON-RPC 2.0 请求，根据 method 路由到对应处理器。
    支持的 method：
      - initialize: 握手初始化
      - tools/list: 列出所有工具
      - tools/call: 调用工具
      - resources/list: 列出知识库资源
      - resources/read: 读取资源内容
      - ping: 心跳
    """
    body = request.get_json(silent=True) or {}
    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    # 路由到对应处理器
    handler = _METHOD_HANDLERS.get(method)
    if not handler:
        return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    try:
        result = handler(params)
        return _jsonrpc_result(req_id, result)
    except Exception as e:
        return _jsonrpc_error(req_id, -32603, f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Method handlers
# ---------------------------------------------------------------------------

def _handle_initialize(params: dict) -> dict:
    """握手初始化。"""
    return {
        "protocolVersion": "2024-11-05",
        "serverInfo": _SERVER_INFO,
    }


def _handle_tools_list(params: dict) -> dict:
    """列出所有可用工具。"""
    tools = list_all_mcp_tools()
    return {"tools": tools}


def _handle_tools_call(params: dict) -> dict:
    """调用指定工具。"""
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if not tool_name:
        raise ValueError("Missing tool name")

    # 构建默认 state（MCP 调用无用户上下文）
    state = {
        "role": params.get("role", "public"),
        "user_id": params.get("user_id", 0),
        "kb_id": params.get("kb_id"),
        "last_hits": [],
    }

    result = call_mcp_tool(tool_name, state, **arguments)
    return {
        "content": [
            {"type": "text", "text": result},
        ],
    }


def _handle_resources_list(params: dict) -> dict:
    """列出知识库文档资源。"""
    resources = list_knowledge_resources()
    return {"resources": resources}


def _handle_resources_read(params: dict) -> dict:
    """读取指定资源内容。"""
    uri = params.get("uri", "")
    if not uri:
        raise ValueError("Missing resource URI")

    # 从 URI 提取 doc_id：knowledge://123
    doc_id_str = uri.replace("knowledge://", "")
    try:
        doc_id = int(doc_id_str)
    except ValueError:
        raise ValueError(f"Invalid resource URI: {uri}")

    content = read_knowledge_resource(doc_id)
    return {
        "contents": [
            {"uri": uri, "mimeType": "text/plain", "text": content},
        ],
    }


def _handle_ping(params: dict) -> dict:
    """心跳。"""
    return {}


# Method → handler 映射
_METHOD_HANDLERS = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
    "resources/list": _handle_resources_list,
    "resources/read": _handle_resources_read,
    "ping": _handle_ping,
}


# ---------------------------------------------------------------------------
# JSON-RPC 响应构建
# ---------------------------------------------------------------------------

def _jsonrpc_result(req_id, result: dict) -> dict:
    """构建 JSON-RPC 成功响应。"""
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id, code: int, message: str) -> dict:
    """构建 JSON-RPC 错误响应。"""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }
