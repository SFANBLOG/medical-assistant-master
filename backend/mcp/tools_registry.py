"""
MCP 工具注册适配层。

桥接现有 tools.py 的 Tool 类和 MCP 协议的 tools/list、tools/call。
"""
from backend.agent import tools as toolmod


def tool_to_mcp_schema(tool: toolmod.Tool) -> dict:
    """将 Tool 转为 MCP tools/list 返回的 schema 格式。

    MCP 工具 schema 格式：
    {
        "name": str,
        "description": str,
        "inputSchema": { JSON Schema }
    }
    """
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.parameters,
    }


def list_all_mcp_tools() -> list[dict]:
    """返回所有工具的 MCP 格式 schema。"""
    return [tool_to_mcp_schema(t) for t in toolmod.TOOLS]


def call_mcp_tool(tool_name: str, state: dict, **kwargs) -> str:
    """通过 MCP 接口调用工具。

    桥接到现有 tools.py 的 run_tool()，确保 MCP 调用与内部调用行为一致。
    """
    return toolmod.run_tool(state, tool_name, **kwargs)
