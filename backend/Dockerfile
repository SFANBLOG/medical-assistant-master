FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

# torch / numpy 的 OpenMP 运行时需要 libgomp1（Milvus 客户端不依赖；本地向量模型依赖）
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt && pip install gunicorn==22.0.0

COPY . .

EXPOSE 8010

# gthread 使 SSE 流式请求可并发；--timeout 300 应对长时间生成
CMD ["gunicorn", "-b", "0.0.0.0:8010", "--worker-class", "gthread", "--threads", "8", "--timeout", "300", "app:app"]
