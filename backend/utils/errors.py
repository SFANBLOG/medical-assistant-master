"""统一错误处理。"""


class ApiError(Exception):
    """携带 HTTP 状态码的业务异常。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(e):
        return {"error": e.message}, e.status

    @app.errorhandler(404)
    def handle_404(e):
        return {"error": "接口不存在"}, 404

    @app.errorhandler(405)
    def handle_405(e):
        return {"error": "请求方法不允许"}, 405

    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.exception("未捕获异常: %s", e)
        return {"error": "服务器内部错误"}, 500
