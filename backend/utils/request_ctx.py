"""请求级上下文：以 contextvar 传播「来源 IP」，供审计服务在无 Flask 请求上下文时读取。

FastAPI 中间件在事件循环里为每个请求 set，同步端点经 anyio 线程池执行时上下文会被
自动复制（copy_context），因此 audit_service._client_ip() 在端点线程内仍能读到值，
调用方（路由 / chat_service 等）无需感知，也不必逐个把 request 传下去。
"""
from contextvars import ContextVar

# 默认空串：离线脚本（seed、验证）无请求上下文时读到空串，与原 Flask 行为一致
client_ip_var: ContextVar[str] = ContextVar("client_ip", default="")
