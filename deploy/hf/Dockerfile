# =====================================================================
#  医智助手 · 单容器演示镜像（Hugging Face Spaces / 任意 PaaS 通用）
#  前端 Vite 构建产物由 Flask 直接托管（SERVE_FRONTEND=1），
#  后端 SQLite + NumpyStore + 哈希向量，零外部依赖，播种即用。
#  构建上下文 = 项目根目录。
# =====================================================================

# ---------- 阶段 1：前端构建 ----------
FROM node:20-alpine AS fe
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 阶段 2：后端 + 静态托管 ----------
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 精简依赖（剔除 pymilvus/torch/PyMySQL 等重依赖，代码内惰性导入自动降级）
COPY backend/requirements-lite.txt /app/backend/
RUN pip install -r backend/requirements-lite.txt

# 后端代码与 gunicorn 入口
COPY backend/ /app/backend/
COPY wsgi.py gunicorn.conf.py /app/

# 前端构建产物（Flask 经 SERVE_FRONTEND=1 直接托管）
COPY --from=fe /fe/dist /app/frontend/dist

# 演示模式默认配置：SQLite + NumpyStore + 内置哈希向量 + 离线兜底生成。
# 可选增强：在 Space 的 Settings → Variables 配置 OPENAI_API_KEY /
# OPENAI_BASE_URL / OPENAI_CHAT_MODEL（任意 OpenAI 兼容端点）即可启用真 LLM。
# GUNICORN_WORKERS=1：NumpyStore 为进程内内存 + pickle 持久化，
# 单 worker（gthread 16 线程）避免多进程写 pkl 互相覆盖、上传后检索不一致。
ENV DB_TYPE=sqlite \
    MILVUS_ENABLE=0 \
    SERVE_FRONTEND=1 \
    OPENAI_EMBED_MODEL= \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=16 \
    GUNICORN_TIMEOUT=300

EXPOSE 8010
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
