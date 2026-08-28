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
        threading.Thread(target=_warmup_vectorstore, daemon=True).start()
    except Exception:
        _warmup_vectorstore()


def main():
    init_database()
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=config.BACKEND_PORT,
        debug=True,
        threaded=True,
    )


if __name__ == "__main__":
    main()
