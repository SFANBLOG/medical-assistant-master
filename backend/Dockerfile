FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

# Chroma 的 ONNX 运行时在 slim 镜像上需要 libgomp1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt && pip install gunicorn==22.0.0

COPY . .

EXPOSE 8010

# gthread 使 SSE 流式请求可并发；--timeout 300 应对长时间生成
CMD ["gunicorn", "-b", "0.0.0.0:8010", "--worker-class", "gthread", "--threads", "8", "--timeout", "300", "app:app"]
