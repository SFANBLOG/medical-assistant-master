"""
Gunicorn 入口：docker 中通过 gunicorn wsgi:app 启动。
等价于原 python -m backend 的 main()：先建库建表 + 播种演示数据，再创建 Flask 应用。
"""
import os
import sys

# 确保项目根目录在 sys.path，使 `backend` 包可被导入。
# 平台以 gunicorn wsgi:app 启动，工作目录不一定为项目根，若不显式加入会报
# ModuleNotFoundError: No module named 'backend'。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import app

# backend.app 在被导入时（非 __main__）已完成 init_database() + create_app()，
# 这里直接复用同一模块级 app 实例，避免重复建库/重复创建应用。

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8010)