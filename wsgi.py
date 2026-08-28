"""
Gunicorn 入口：docker 中通过 gunicorn wsgi:app 启动。
等价于原 python -m backend 的 main()：先建库建表 + 播种演示数据，再创建 Flask 应用。
"""
from backend.app import create_app, init_database

# 启动即初始化数据库（建库/建表/播种），与本地运行行为保持一致
init_database()

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8010)
