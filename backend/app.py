"""
医智助手 · 后端入口（FastAPI / ASGI）

启动后自动建库建表 + 播种演示数据。
运行: python -m backend  （从项目根目录执行）→  http://127.0.0.1:8010
生产: gunicorn -c gunicorn.conf.py wsgi:app（worker_class=uvicorn.workers.UvicornWorker）
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import config
# 导入路由（APIRouter）
from backend.routes.auth_bp import router as auth_router
from backend.routes.chat_bp import router as chat_router
from backend.routes.dashboard_bp import router as dashboard_router
from backend.routes.kb_bp import router as kb_router
from backend.routes.medical_bp import router as medical_router
from backend.routes.review_bp import router as review_router
from backend.utils.db import init_schema, DB_TYPE
from backend.utils.errors import register_error_handlers
from backend.utils.request_ctx import client_ip_var


def create_app() -> FastAPI:
    # 单容器演示部署：SERVE_FRONTEND=1 且前端构建产物存在时，由 ASGI 应用直接托管 dist。
    # 前端为 hash 路由 + 相对路径 /api，同源服务无需 Nginx 反代与 history fallback。
    serve_dist = config.SERVE_FRONTEND and (config.FRONTEND_DIST / "index.html").is_file()

    app = FastAPI(title="医智助手", docs_url=None, redoc_url=None)

    # CORS 全开
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 请求来源 IP 写入 contextvar，供审计服务在无请求上下文时读取（兼容反向代理）
    @app.middleware("http")
    async def _client_ip_middleware(request: Request, call_next):
        fwd = request.headers.get("X-Forwarded-For", "")
        ip = (fwd.split(",")[0].strip() if fwd
              else (request.client.host if request.client else ""))
        token = client_ip_var.set(ip or "")
        try:
            return await call_next(request)
        finally:
            client_ip_var.reset(token)

    # 注册路由
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(chat_router, prefix="/api/chat")
    app.include_router(kb_router, prefix="/api/kb")
    app.include_router(medical_router, prefix="/api/medical")
    app.include_router(dashboard_router, prefix="/api/dashboard")
    app.include_router(review_router, prefix="/api/review")

    # 统一错误处理（ApiError / 参数校验 / HTTPException / 未捕获异常）
    register_error_handlers(app)

    # 健康检查
    @app.get("/api/health")
    def health():
        return {"status": "ok", "db_type": DB_TYPE}

    # 向量库状态
    @app.get("/api/vector/status")
    def vector_status():
        from backend.rag.vectorstore import get_vectorstore
        vs = get_vectorstore()
        return {
            "backend": vs.__class__.__name__,
            "milvus_enabled": config.MILVUS_ENABLE,
            "embed_model": config.OPENAI_EMBED_MODEL or "hash (builtin)",
            "chat_model": config.OPENAI_CHAT_MODEL,
        }

    # 单容器模式：挂载前端静态站点（html=True 使 "/" 直接返回 index.html）。
    # 必须在所有 /api 路由注册之后挂载，"/" 兜底才不会抢占 API 匹配。
    if serve_dist:
        app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIST), html=True), name="static")

    return app


def init_database():
    """初始化数据库：建库 + 建表 + 播种。"""
    print("=" * 60)
    print("  医智助手 · 后端启动")
    print("=" * 60)
    print(f"  数据库类型: {DB_TYPE}")
    print(f"  向量库: {'Milvus' if config.MILVUS_ENABLE else 'NumpyStore'}")
    print(f"  聊天模型: {config.OPENAI_CHAT_MODEL}")
    print(f"  嵌入模型: {config.OPENAI_EMBED_MODEL or '哈希向量 (内置)'}")
    print("=" * 60)

    # 1. 建表
    init_schema()

    # 2. 检查是否需要播种
    from backend.utils.db import fetchone
    row = fetchone("SELECT COUNT(*) AS cnt FROM users")
    user_count = row["cnt"] if row else 0
    if user_count == 0:
        print("[DB] 检测到空数据库，开始播种演示数据...")
        from backend.seed import seed_all
        seed_all()
    else:
        print(f"[DB] 数据库已有 {user_count} 个用户，跳过播种。")

    # 3. 初始化向量库（后台线程预热，避免 Milvus collection.load 阻塞 worker 启动）
    def _warmup_vectorstore():
        try:
            from backend.rag.vectorstore import get_vectorstore
            vs = get_vectorstore()
            print(f"[RAG] 向量库后端: {vs.__class__.__name__}")
        except Exception as e:
            print(f"[RAG] 向量库初始化失败（将使用兜底）: {e}")

    try:
        import threading
        t = threading.Thread(target=_warmup_vectorstore, daemon=True)
        t.start()
        # 关键修复（gunicorn --preload + SSE 检索挂起）：
        # master 必须等向量库预热完成后再 fork worker。若 fork 发生时 warmup
        # 线程仍在加载 BGE 模型 / 建立 Milvus 连接，worker 会继承半初始化的
        # torch 线程池状态，首个 SSE 请求在 embedder.encode 处挂起（90s+ 无响应）。
        # join 后所有单例在 fork 前完全就绪，worker 内共享只读模型、post_fork
        # 各自重建 Milvus 连接，均安全。
        t.join(timeout=180)
    except Exception:
        _warmup_vectorstore()


def main():
    init_database()
    import uvicorn
    # 本地启动走 uvicorn；确需改代码热重载时设 FLASK_USE_RELOADER=1。
    # 生产（Docker/gunicorn）不经过 main()，由 wsgi:app + UvicornWorker 承载。
    uvicorn.run(
        create_app(),
        host="0.0.0.0",
        port=config.BACKEND_PORT,
        reload=config.FLASK_USE_RELOADER,
    )


if __name__ == "__main__":
    main()
