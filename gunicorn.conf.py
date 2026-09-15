"""
Gunicorn 配置：--preload 模式下的 fork 安全修复。

问题背景：
--preload 下 gunicorn master 在 fork 前执行 wsgi.py（模块级 init_database()），
其中 _warmup_vectorstore() 后台线程创建了 MilvusStore 单例 —— pymilvus
MilvusClient 的 gRPC channel 在 master 进程建立；fork 出 4 个 worker 后，
所有 worker 共享同一个 gRPC channel。pymilvus 的 channel 非多进程安全，
多 worker 并发查询（混合检索 retrieve -> vs.search）会挂起，
表现：SSE 请求 90s+ 无任何字节返回（citations 事件都发不出来）。

修复方式：
post_fork 钩子把继承自 master 的 vectorstore 单例重置为 None，
各 worker 在首个请求时各自新建 MilvusClient 连接（互不共享，fork 安全）。
嵌入模型（torch 只读推理）与 reranker 保持共享，避免每个 worker 重复加载
BGE 模型导致内存翻倍。
"""
import os

# 监听端口：优先读平台注入的 PORT（PocketBay 等托管平台会指定 PORT 并要求绑定 0.0.0.0），
# 未设置时回落到后端默认端口 8010（本地 compose / 直跑 gunicorn 行为不变）。
bind = f"0.0.0.0:{os.getenv('PORT') or os.getenv('BACKEND_PORT') or '8010'}"
workers = int(os.getenv("GUNICORN_WORKERS", "4"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
# SSE 流式回答预留充足时长：默认 120s 可能在 LLM 生成长回答时掐断流
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))
# 与 Dockerfile CMD 的历史 --preload 保持一致（建库建表/播种/Milvus 预热在 master 完成）
preload_app = True


def post_fork(server, worker):
    """fork 后重置进程级单例连接，避免 worker 共享 master 的 Milvus gRPC 连接。"""
    try:
        import backend.rag.vectorstore as vsmod
        vsmod._store = None
        print(
            f"[Gunicorn] worker {worker.pid} 已重置 vectorstore 单例（fork 安全）",
            flush=True,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[Gunicorn] post_fork 重置 vectorstore 失败: {e}", flush=True)
