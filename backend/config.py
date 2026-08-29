"""
全局配置加载：从 .env 文件读取，不覆盖已存在的环境变量。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录（backend/ 的父目录 或 backend/ 自身）
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent

# 加载 .env（优先 backend/.env，其次 项目根/.env）
_env_backend = BACKEND_DIR / ".env"
_env_root = PROJECT_DIR / ".env"
if _env_backend.exists():
    load_dotenv(_env_backend, override=False)
if _env_root.exists():
    load_dotenv(_env_root, override=False)

# ---- 数据库 ----
DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()
DATABASE_NAME = os.getenv("DATABASE_NAME", "medical-assistant-master")
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "123456")

# ---- 向量库（Milvus）----
MILVUS_ENABLE = os.getenv("MILVUS_ENABLE", "1") == "1"
MILVUS_HOST = os.getenv("MILVUS_HOST", "127.0.0.1")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
# 连接超时（秒）：本地未启动 Milvus 时快速失败并降级，避免阻塞启动。
MILVUS_CONNECT_TIMEOUT = int(os.getenv("MILVUS_CONNECT_TIMEOUT", "3"))

# ---- 聊天 / 向量化 ----
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "deepseek-chat")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "")

# ---- RAG 参数 ----
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))
# 是否把「章节路径」拼到 chunk 文本前（如「第3章 糖尿病 > 3.1 分型」）
CHUNK_HEADING_PREFIX = os.getenv("CHUNK_HEADING_PREFIX", "1") == "1"

# ---- PDF 解析 ----
# 是否清洗跨页重复的页眉 / 页脚与页码行
PDF_STRIP_HEADER_FOOTER = os.getenv("PDF_STRIP_HEADER_FOOTER", "1") == "1"
# 整篇 PDF 提取出的字符数低于该值时，视为扫描件（无文本层）
PDF_MIN_TEXT_CHARS = int(os.getenv("PDF_MIN_TEXT_CHARS", "50"))

TOP_K = int(os.getenv("TOP_K", "5"))
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.30"))

# ---- 混合检索（BM25 稀疏 + 稠密向量 + Cross-Encoder 重排）----
# 阶段1：两个分支各召回 top-N
BM25_TOP_K = int(os.getenv("BM25_TOP_K", "30"))
DENSE_TOP_K = int(os.getenv("DENSE_TOP_K", "30"))
# 稠密分支的相似度下限（仅过滤纯噪声，低相关交由重排阶段裁决）
DENSE_MIN_SIMILARITY = float(os.getenv("DENSE_MIN_SIMILARITY", "0.0"))
# 阶段3：Cross-Encoder 重排后保留的条数，与相关性下限
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
RERANK_MIN_SCORE = float(os.getenv("RERANK_MIN_SCORE", "0.12"))
# 重排融合权重（稠密余弦 + BM25 归一化 + 词法重叠）
RERANK_W_DENSE = float(os.getenv("RERANK_W_DENSE", "0.55"))
RERANK_W_BM25 = float(os.getenv("RERANK_W_BM25", "0.30"))
RERANK_W_LEXICAL = float(os.getenv("RERANK_W_LEXICAL", "0.15"))

# ---- 服务端口 ----
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8010"))

# ---- JWT ----
JWT_SECRET = os.getenv("JWT_SECRET", "medical-assistant-secret-key-2024")
JWT_EXP_HOURS = 24

# ---- 路径 ----
DATA_DIR = BACKEND_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
MODEL_DIR = DATA_DIR / "models"
SQLITE_PATH = DATA_DIR / f"{DATABASE_NAME}.db"

# 确保目录存在
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ---- Milvus 集合名 ----
MILVUS_COLLECTION = "medical_chunks"
