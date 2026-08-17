"""应用配置：全部通过环境变量注入，便于本地与 Docker 部署。"""
import os

# 加载项目根目录或 backend/ 下的 .env（不覆盖已存在的环境变量，Docker 注入优先）
try:
    from dotenv import load_dotenv

    _BASE = os.path.dirname(os.path.abspath(__file__))
    for _p in (os.path.join(os.path.dirname(_BASE), ".env"), os.path.join(_BASE, ".env")):
        if os.path.exists(_p):
            load_dotenv(_p)
except ImportError:  # 未安装 python-dotenv 时静默跳过
    pass


class Config:
    # ---- 安全 ----
    # ⚠️ 生产务必替换环境变量JWT_SECRET，至少32字节！下面仅本地开发临时示例
    JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-secret-32bytes-long-key-xxxx")
    JWT_ALGO = "HS256"
    JWT_EXPIRES_HOURS = int(os.environ.get("JWT_EXPIRES_HOURS", "24"))

    # ---- 路径 ----
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
    DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(DATA_DIR, "medical-assistant-master.db"))
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(DATA_DIR, "uploads"))
    CHROMA_DIR = os.environ.get("CHROMA_DIR", os.path.join(DATA_DIR, "chroma"))

    # ---- LLM（OpenAI 兼容接口）。base_url/api_key 为空 -> 离线兜底 ----
    # 生产环境请通过环境变量注入，勿把真实密钥写进源码。
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "deepseek-v4-flash")
    # 向量化：留空 -> 内置确定性哈希向量（无需模型、离线可用，维度 EMBED_DIM）。
    # 也可填写本地 sentence-transformers 模型名（如 all-MiniLM-L6-v2，维度384）。
    OPENAI_EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "")

    # ---- RAG 参数 ----
    EMBED_DIM = int(os.environ.get("EMBED_DIM", "256"))
    CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "50"))
    TOP_K = int(os.environ.get("TOP_K", "5"))

    # ---- 上传 ----
    ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx"}
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024

    # ---- 跨域 ----
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # ---- 首启自动播种演示数据 ----
    AUTO_SEED = os.environ.get("AUTO_SEED", "1") == "1"