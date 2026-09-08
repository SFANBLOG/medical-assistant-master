"""
医智助手 · 后端入口

启动后自动建库建表 + 播种演示数据。
运行: python -m backend  （从项目根目录执行）→  http://127.0.0.1:8010
"""
from flask import Flask
from flask_cors import CORS

from backend import config
from backend.utils.db import init_schema, DB_TYPE

# 导入蓝图
from backend.routes.auth_bp import auth_bp
from backend.routes.chat_bp import chat_bp
from backend.routes.kb_bp import kb_bp
from backend.routes.medical_bp import medical_bp
from backend.routes.dashboard_bp import dashboard_bp
from backend.routes.agent_bp import agent_bp
from backend.routes.review_bp import review_bp
from backend.mcp.server import mcp_bp
from backend.utils.errors import register_error_handlers


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB

    # CORS 全开
    CORS(app, supports_credentials=True, origins="*")

    # 注册蓝图
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(kb_bp, url_prefix="/api/kb")
    app.register_blueprint(medical_bp, url_prefix="/api/medical")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(agent_bp, url_prefix="/api/agent")
    app.register_blueprint(review_bp, url_prefix="/api/review")
    app.register_blueprint(mcp_bp, url_prefix="/api")

    # 统一错误处理（APIError / 404 / 405 / 未捕获异常）
    register_error_handlers(app)

    # 健康检查
    @app.route("/api/health")
    def health():
        return {"status": "ok", "db_type": DB_TYPE}

    # 向量库状态
    @app.route("/api/vector/status")
    def vector_status():
        from backend.rag.vectorstore import get_vectorstore
        vs = get_vectorstore()
        return {
            "backend": vs.__class__.__name__,
            "milvus_enabled": config.MILVUS_ENABLE,
            "embed_model": config.OPENAI_EMBED_MODEL or "hash (builtin)",
            "chat_model": config.OPENAI_CHAT_MODEL,
        }

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
    app = create_app()
    # 本地启动：保留交互调试器（debug=True 由 FLASK_DEBUG 控制），但默认关闭
    # watchdog 自动重载（use_reloader=False）——Windows 下文件监视会把目录里任何动静
    # （临时脚本增删、.venv 写入）当成代码变更，反复重启导致启动横幅与模型加载重复输出。
    # 确需热重载：FLASK_USE_RELOADER=1。生产（Docker/gunicorn）不经过 app.run。
    app.run(
        host="0.0.0.0",
        port=config.BACKEND_PORT,
        debug=config.FLASK_DEBUG,
        use_reloader=config.FLASK_USE_RELOADER,
        threaded=True,
    )


if __name__ == "__main__":
    main()
