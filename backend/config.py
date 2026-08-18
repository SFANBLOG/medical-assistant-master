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

    # ---- 数据库（默认 MySQL，可设 DB_TYPE=sqlite 使用本地 SQLite 兜底）----
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
    DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(DATA_DIR, "medical-assistant-master.db"))
    DATABASE_NAME = os.environ.get("DATABASE_NAME", "medical-assistant-master")
    DB_TYPE = os.environ.get("DB_TYPE", "mysql").lower()
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "123456")
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(DATA_DIR, "uploads"))
    # 向量库落盘目录：NumpyStore 兜底时使用（Milvus 模式不使用本地落盘）
    VECTOR_DIR = os.environ.get("VECTOR_DIR", os.path.join(DATA_DIR, "vectors"))

    # ---- 向量库（Milvus，首选）----
    # 取消 ChromaDB 存储模式。MILVUS_ENABLE=0 时直接使用 NumpyStore 兜底。
    MILVUS_ENABLE = os.environ.get("MILVUS_ENABLE", "1")
    MILVUS_HOST = os.environ.get("MILVUS_HOST", "127.0.0.1")
    MILVUS_PORT = int(os.environ.get("MILVUS_PORT", "19530"))
    MILVUS_DB = os.environ.get("MILVUS_DB", "default")
    MILVUS_COLLECTION = os.environ.get("MILVUS_COLLECTION", "")  # 空 -> 使用默认集合名

    # ---- LLM（OpenAI 兼容接口）。base_url/api_key 为空 -> 离线兜底 ----
    # 生产环境请通过环境变量注入，勿把真实密钥写进源码。
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-df59d4d083534657acf6bbce369e01dc")
    OPENAI_CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "deepseek-v4-flash")
    # 向量化模型：可以是本地模型目录（如 data/models/bge-base-zh-v1.5，会解析为绝对路径），
    # 或 HuggingFace 模型 id（如 BAAI/bge-base-zh-v1.5，自动从 hf-mirror.com 下载）。
    # 留空 -> 内置确定性哈希向量（离线可用，维度 EMBED_DIM），但语义检索效果差。
    # 推荐 BAAI/bge-base-zh-v1.5（中文语义检索，维度 768；如需更强可换 bge-large-zh-v1.5 并设 EMBED_DIM=1024）。
    _EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "BAAI/bge-base-zh-v1.5")
    if _EMBED_MODEL and not os.path.isabs(_EMBED_MODEL) and not _EMBED_MODEL.startswith(("http", "BAAI/", "sentence-transformers/")):
        _candidate = os.path.join(_BASE, _EMBED_MODEL)
        if os.path.isdir(_candidate):
            OPENAI_EMBED_MODEL = os.path.abspath(_candidate)
        else:
            OPENAI_EMBED_MODEL = _EMBED_MODEL
    else:
        OPENAI_EMBED_MODEL = _EMBED_MODEL

    # ---- RAG 参数 ----
    # EMBED_DIM 必须与向量模型输出维度一致：BAAI/bge-base-zh-v1.5 = 768，
    # BAAI/bge-large-zh-v1.5 = 1024；若留空模型用哈希向量兜底，维度取本值。
    EMBED_DIM = int(os.environ.get("EMBED_DIM", "768"))
    # CHUNK_SIZE 按字符数切分：bge-* 最长 512 token，中文约 1.2 字/token，
    # 取 500 字符保证切片不超长被截断；CHUNK_OVERLAP 相邻切片重叠，保留上下文连贯。
    CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "80"))
    TOP_K = int(os.environ.get("TOP_K", "5"))
    # 召回相似度下限（cosine 相似度，0~1）：低于该值视为无关文档，不进入回答上下文。
    MIN_SIMILARITY = float(os.environ.get("MIN_SIMILARITY", "0.30"))

    # ---- 上传 ----
    ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx"}
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024

    # ---- 跨域 ----
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # ---- 首启自动播种演示数据 ----
    AUTO_SEED = os.environ.get("AUTO_SEED", "1") == "1"
    print(f"API_KEY: {OPENAI_API_KEY[:8]}...{OPENAI_API_KEY[-4:] if OPENAI_API_KEY else ''}")
    print("EMBED_MODEL:", OPENAI_EMBED_MODEL)
    print("BASE_URL:", OPENAI_BASE_URL)
    print("VECTOR_STORE: Milvus" if MILVUS_ENABLE not in ("0", "false", "False") else "VECTOR_STORE: NumpyStore")
