"""
MCP Client 实现。

供智能体内部调用外部 MCP 工具（如接入第三方医疗 API）。
当前版本主要用于统一本地工具调用接口，未来可扩展接入外部 MCP 服务。
"""
from typing import Optional

import requests


class MCPClient:
    """MCP 客户端：连接外部 MCP Server，获取工具列表并调用。

    使用场景：
      - 当前版本：统一本地工具调用接口（自调用）
      - 未来扩展：接入外部医疗 MCP 服务（药品数据库、医保查询等）
    """

    def __init__(self, server_url: str, auth_token: Optional[str] = None):
        """
        Args:
            server_url: MCP Server 的 URL（如 http://localhost:8010/api/mcp）
            auth_token: 可选的认证 token
        """
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self._request_id = 0
        self._tools_cache: Optional[list] = None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _call(self, method: str, params: Optional[dict] = None) -> dict:
        """发送 JSON-RPC 请求。"""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        resp = requests.post(
            self.server_url,
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"MCP Error {err.get('code')}: {err.get('message')}")

        return data.get("result", {})

    def initialize(self) -> dict:
        """握手初始化。"""
        return self._call("initialize")

    def list_tools(self, force_refresh: bool = False) -> list[dict]:
        """获取工具列表（带缓存）。

        Args:
            force_refresh: 强制刷新缓存

        Returns:
            list[dict]: 工具 schema 列表
        """
        if self._tools_cache is None or force_refresh:
            result = self._call("tools/list")
            self._tools_cache = result.get("tools", [])
        return self._tools_cache

    def call_tool(self, tool_name: str, arguments: Optional[dict] = None, **kwargs) -> str:
        """调用指定工具。

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            **kwargs: 额外参数（合并到 arguments）

        Returns:
            str: 工具返回的文本结果
        """
        args = {**(arguments or {}), **kwargs}
        result = self._call("tools/call", {"name": tool_name, "arguments": args})
        contents = result.get("content", [])
        if contents:
            return contents[0].get("text", "")
        return ""

    def list_resources(self) -> list[dict]:
        """列出可用资源。"""
        result = self._call("resources/list")
        return result.get("resources", [])

    def read_resource(self, uri: str) -> str:
        """读取指定资源内容。"""
        result = self._call("resources/read", {"uri": uri})
        contents = result.get("contents", [])
        if contents:
            return contents[0].get("text", "")
        return ""

    def ping(self) -> bool:
        """心跳检测。"""
        try:
            self._call("ping")
            return True
        except Exception:
            return False


def create_local_client(base_url: str = "http://127.0.0.1:8010") -> MCPClient:
    """创建指向本地 MCP Server 的客户端。"""
    return MCPClient(f"{base_url}/api/mcp")
