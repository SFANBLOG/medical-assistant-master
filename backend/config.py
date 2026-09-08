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
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "auto")
# 值 "auto" 表示自动在 MODEL_DIR 下搜索已下载的 BGE 模型（优先 bge-small-zh-v1.5）；
# 设为具体路径或 HuggingFace repo_id 可覆盖自动检测。

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
# 5→8：实测重排分数第 6~8 条仍达 0.66~0.69（高相关），原先 5 条会砍掉它们，
# 扩到 8 条可让 LLM 拿到更完整的上下文，且候选池 30+30 充足、不增加 CE 调用次数。
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "8"))
# 相关性下限：低于此分的候选不进入 LLM 上下文（过滤噪声 → 提升回答质量）。
# 融合算法下相关文档普遍 >=0.90，不相关 <0.45，0.45 可干净切分两者。
RERANK_MIN_SCORE = float(os.getenv("RERANK_MIN_SCORE", "0.45"))
# 重排融合权重（稠密余弦 + BM25 归一化 + 词法重叠）
RERANK_W_DENSE = float(os.getenv("RERANK_W_DENSE", "0.55"))
RERANK_W_BM25 = float(os.getenv("RERANK_W_BM25", "0.30"))
RERANK_W_LEXICAL = float(os.getenv("RERANK_W_LEXICAL", "0.15"))
# Cross-Encoder 模型路径（留空或 "auto" 则用融合模式；推荐 BAAI/bge-reranker-v2-min）
RERANK_MODEL_PATH = os.getenv("RERANK_MODEL_PATH", "auto")
# 值 "auto" 表示自动在 MODEL_DIR 下搜索已下载的 CE 模型，找不到则用增强融合。
# 是否启用 Cross-Encoder 作为增强信号（默认关闭）：
#   - bge-reranker-* 类模型在 CPU 上单查询需 14~31s，且原始 sigmoid 分数被压缩在
#     0.5~0.73 区间、对"非常相关/较相关"区分度差，直接替换融合反而会让展示相关度
#     从 95%+ 掉到 ~73%。故默认关闭，仅作可选增强（与融合取 max，只升不降）。
#   - 设为 true 且模型存在时，CE 仅作为"增强boost"，绝不拉低融合给出高分的相关文档。
RERANK_USE_CE = os.getenv("RERANK_USE_CE", "false").lower() in ("1", "true", "yes", "on")

# ---- Agent 架构 ----
# v1: 原有单体编排器（roles.py 关键字路由）
# v2: 新架构（Supervisor + 子智能体 + 技能系统）
AGENT_MODE = os.getenv("AGENT_MODE", "v2").lower()

# ---- 服务端口 ----
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8010"))

# ---- 本地 Flask 运行模式（仅 app.run 生效；Docker/gunicorn 走 wsgi 入口，不经这里）----
# Windows 下 debug=True 会连带开启 watchdog 文件监视自动重载，对目录动静极敏感：
# 任何临时脚本增删（如 diag_models.py）、.venv/site-packages 写入都会触发
# "Detected change → Restarting"，整服务反复重启 → 启动横幅/模型加载重复打印，并偶发
# WinError 10038。故默认保留交互调试器（错误页 + PIN）但关闭自动重载；
# 确需改代码热重载时设 FLASK_USE_RELOADER=1。
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "1").lower() in ("1", "true", "yes", "on")
FLASK_USE_RELOADER = os.getenv("FLASK_USE_RELOADER", "0").lower() in ("1", "true", "yes", "on")

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
