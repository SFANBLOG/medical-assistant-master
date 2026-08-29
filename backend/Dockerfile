# =====================================================================
#  医智助手 · 后端镜像
#  Flask + Milvus 客户端 + sentence-transformers（本地向量模型）
#  多阶段构建：构建阶段安装依赖，运行阶段裁剪到最小体积。
# =====================================================================

# ---------- 阶段 1：构建依赖 ----------
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# 先用独立的构建虚拟环境安装依赖，避免污染运行阶段，便于最终镜像瘦身
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --default-timeout=100 \
    && pip install --no-cache-dir -r requirements.txt gunicorn==22.0.0 -i https://pypi.tuna.tsinghua.edu.cn/simple --default-timeout=100


# ---------- 阶段 2：运行时 ----------
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PATH="/opt/venv/bin:$PATH" \
    HF_ENDPOINT="https://hf-mirror.com" \
    PIP_NO_CACHE_DIR=1

# torch / numpy 的 OpenMP 运行时需要 libgomp1（本地向量模型依赖）
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 复制构建阶段安装好的虚拟环境
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# 以非 root 用户运行，降低容器内提权风险
# /data 由 docker-compose 挂载命名卷，首次创建时继承镜像中该目录的属主（app:app）
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data/uploads /data/vectors /data/models \
    && chown -R app:app /app /data

USER app

COPY --chown=app:app . .

EXPOSE 8010

# gthread 使 SSE 流式请求可并发；--timeout 300 应对长时间生成
CMD ["gunicorn", "-b", "0.0.0.0:8010", "--worker-class", "gthread", "--threads", "8", "--timeout", "300", "app:app"]
