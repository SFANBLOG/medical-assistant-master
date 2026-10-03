"""
部署入口：gunicorn 通过 `gunicorn -c gunicorn.conf.py wsgi:app` 启动，
worker_class 为 uvicorn.workers.UvicornWorker（ASGI）。

等价于原 python -m backend 的 main()：先建库建表 + 播种演示数据，再创建 ASGI 应用。
"""
from backend.app import create_app, init_database

# 启动即初始化数据库（建库/建表/播种），与本地运行行为保持一致
init_database()

app = create_app()
