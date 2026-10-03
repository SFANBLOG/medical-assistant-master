"""统一错误处理（FastAPI 版）。

把业务异常、参数校验失败、HTTP 异常、兜底异常统一归一成 {"error": ...} JSON 响应，
保持与旧 Flask 版逐字一致的对外错误契约（中文文案 + 状态码）。
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

_logger = logging.getLogger("medical-assistant")


class ApiError(Exception):
    """携带 HTTP 状态码的业务异常。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


# Starlette 默认英文文案 → 还原旧实现的中文文案
_CN_BY_STATUS = {404: "接口不存在", 405: "请求方法不允许"}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle_api_error(request: Request, exc: ApiError):
        return JSONResponse({"error": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError):
        # 与旧契约一致：参数问题统一 400 + 中文提示
        return JSONResponse({"error": "请求参数不合法"}, status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if exc.status_code in _CN_BY_STATUS:
            detail = _CN_BY_STATUS[exc.status_code]
        elif not isinstance(detail, str):
            detail = "请求错误"
        return JSONResponse({"error": detail}, status_code=exc.status_code,
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _handle_uncaught(request: Request, exc: Exception):
        _logger.exception("未捕获异常: %s", exc)
        return JSONResponse({"error": "服务器内部错误"}, status_code=500)
