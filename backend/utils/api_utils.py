"""路由层通用工具：与旧 Flask `request.get_json(silent=True) or {}` 行为等价的请求体依赖。

以异步依赖形式读取并缓存 JSON 体，返回 dict（空/非对象体一律归一为 {}），
因此可注入到同步 `def` 端点，既保留容错语义，又不改变各端点自定义中文校验错误。
"""
from fastapi import Request


async def json_body(request: Request) -> dict:
    """读取 JSON 请求体；解析失败或不是对象时返回 {}（对齐旧 get_json(silent=True) or {})。"""
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001 空体 / 非法 JSON
        return {}
    return data if isinstance(data, dict) else {}
