"""
Gunicorn 配置：适配 PocketBay 等 PaaS 部署。

修复要点：
- 关闭 preload（避免 init_database() 阻塞启动延迟健康检查）
- 使用 sync workers（SQLite + NumpyStore 无 GIL 竞争问题）
- 绑定 0.0.0.0:PORT，接受平台注入的 PORT 环境变量
"""
import os

# 确保项目根目录在模块搜索路径
_chdir = os.path.dirname(os.path.abspath(__file__))
pythonpath = [_chdir]

# PocketBay 部署要求绑定 0.0.0.0:8080（PORT 环境变量由平台注入）
bind = "0.0.0.0:" + os.getenv("PORT", "8080")
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))
# 关闭 preload：避免 init_database() 阻塞导致健康检查超时
preload_app = False


def post_worker_init(worker):
    """worker 启动后打印标识信息。"""
    print(f"[Gunicorn] worker {worker.pid} started", flush=True)
