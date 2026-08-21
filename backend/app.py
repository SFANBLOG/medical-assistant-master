"""医智助手 Flask 服务入口。

本地开发：
    python app.py            # http://127.0.0.1:8010
    python app.py --seed     # 先播种演示数据
"""
import os
import secrets

# 生成一个安全的随机密钥
JWT_SECRET_KEY = secrets.token_hex(32)  # 64字符的 hex 字符串
# huggingface国内镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
import sys

from flask import Flask, g
from flask_cors import CORS

from config import Config
from models.db import init_schema, get_conn
from utils.errors import register_error_handlers


def create_app(config=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config or Config)
    app.config["JSON_AS_ASCII"] = False

    init_schema(app.config)
    register_error_handlers(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from api import register_blueprints

    register_blueprints(app)

    @app.teardown_appcontext
    def _close_db(exc=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    if app.config["AUTO_SEED"]:
        _auto_seed(app)

    return app


def _auto_seed(app) -> None:
    """首次启动（用户表为空）时自动播种演示数据。"""
    try:
        with app.app_context():
            conn = get_conn()
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if count > 0:
                return
        from seed import seed_all

        with app.app_context():
            seed_all(app)
            print("[seed] 演示数据已初始化（患者/医生/护士/群众/管理员 账号，账号密码均为 demo123）")
    except Exception:  # noqa: BLE001
        app.logger.exception("自动播种失败（可稍后手动执行 python seed.py）")


app = create_app()

if __name__ == "__main__":
    if "--seed" in sys.argv:
        from seed import seed_all

        with app.app_context():
            seed_all(app)
        print("[seed] 完成")
    app.run(host="0.0.0.0", port=8010, debug=True, use_reloader=False)
