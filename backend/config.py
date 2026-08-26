"""应用配置：全部通过环境变量注入，便于本地与 Docker 部署。"""
import json
import os

# 模块级基础目录：无论 dotenv 是否可用都必须存在（_resolve_embed_model 依赖）
_BASE = os.path.dirname(os.path.abspath(__file__))

# 加载项目根目录或 backend/ 下的 .env（不覆盖已存在的环境变量，Docker 注入优先）
try:
    from dotenv import load_dotenv

    for _p in (os.path.join(os.path.dirname(_BASE), ".env"), os.path.join(_BASE, ".env")):
        if os.path.exists(_p):
            load_dotenv(_p)
except ImportError:  # 未安装 python-dotenv 时静默跳过
    pass


class Config:
    # ---- 安全 ----
    # ⚠️ 生产务必替换环境变量JWT_SECRET，至少32字节！下面仅本地开发临时示例
    JWT_SECRET = os.environ.get("JWT_SECRET", "93b9c6f957c383f081d0b4c465e2a865a5b424fccc9bd09ec7d0ec01149a85c3")
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

    @staticmethod
    def _resolve_embed_model(name: str) -> str:
        """把配置的向量模型解析为可直接加载的值（本地目录绝对路径 / HF 模型 id）。

        解析优先级（确保项目自带的 data/models 权重一定被用到，而不是去 HuggingFace 下载）：
        1. 已是绝对路径 / 相对路径且对应真实存在的本地目录 -> 直接用；
        2. 在 data/models/ 下按名称匹配（支持 HF id 的最后一段，如
           "BAAI/bge-base-zh-v1.5" -> "data/models/bge-base-zh-v1.5"），命中即用本地模型；
        3. 无本地模型时保留原值（HF id 将尝试下载；下载失败自动回退哈希向量兜底）。
        """
        if not name:
            return name
        # 1) 已存在的本地目录（绝对或相对）
        if os.path.isdir(name):
            return os.path.abspath(name)
        rel = os.path.join(_BASE, name)
        if os.path.isdir(rel):
            return os.path.abspath(rel)
        # 2) 在 data/models 下按名称/片段匹配（最关键：让本地权重优先于远程下载）
        models_dir = os.path.join(_BASE, "data", "models")
        if os.path.isdir(models_dir):
            basename = name.split("/")[-1]
            prefix = basename.split("-")[0]
            for d in sorted(os.listdir(models_dir)):
                full = os.path.join(models_dir, d)
                if not os.path.isdir(full):
                    continue
                if d == name or d == basename or d == name.split("/")[-1] \
                        or d.startswith(prefix) or basename.startswith(d):
                    print(f"[config] 使用本地向量模型：{full}")
                    return os.path.abspath(full)
        # 3) 无本地模型：保留原值（HF id 尝试下载；失败自动哈希兜底）
        return name

    OPENAI_EMBED_MODEL = _resolve_embed_model(_EMBED_MODEL)

    @staticmethod
    def _detect_embed_dim(model: str, fallback: int) -> int:
        """推断向量模型的实际维度：本地目录读 config.json 的 hidden_size，
        知名 bge 系列按名称映射；未知则返回 fallback。"""
        if model:
            if os.path.isdir(model):
                cfg_path = os.path.join(model, "config.json")
                try:
                    with open(cfg_path, encoding="utf-8") as f:
                        hidden = json.load(f).get("hidden_size")
                    if hidden:
                        return int(hidden)
                except Exception:  # noqa: BLE001 读不到配置就按名称推断
                    pass
            low = model.lower()
            for key, dim in (("bge-large", 1024), ("bge-base", 768), ("bge-small", 512), ("bge-m3", 1024)):
                if key in low:
                    return dim
        return fallback

    # ---- RAG 参数 ----
    # EMBED_DIM 必须与向量模型输出维度一致：BAAI/bge-base-zh-v1.5 = 768，
    # BAAI/bge-large-zh-v1.5 = 1024；若留空模型用哈希向量兜底，维度取本值。
    # 启动时自动按模型实际维度校验并修正，避免 .env 与模型维度不一致导致
    # 向量库维度不匹配报错或哈希向量低分检索。
    _EMBED_DIM = int(os.environ.get("EMBED_DIM", "768"))
    _DETECTED_DIM = _detect_embed_dim(OPENAI_EMBED_MODEL, _EMBED_DIM)
    if _DETECTED_DIM != _EMBED_DIM:
        print(f"[config] 警告：EMBED_DIM={_EMBED_DIM} 与向量模型 {OPENAI_EMBED_MODEL!r} "
              f"实际维度 {_DETECTED_DIM} 不一致，已自动修正为 {_DETECTED_DIM}")
    EMBED_DIM = _DETECTED_DIM
    # CHUNK_SIZE 按字符数切分：bge-* 最长 512 token，中文约 1 字/token，
    # 取 380 字符既避免超长截断，又保留较细粒度的语义片段，召回更精准；
    # CHUNK_OVERLAP 相邻切片重叠，保留上下文连贯。
    CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "380"))
    CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "60"))
    TOP_K = int(os.environ.get("TOP_K", "6"))
    # 召回相似度下限（cosine 相似度，0~1）：低于该值视为无关文档，不进入回答上下文。
    MIN_SIMILARITY = float(os.environ.get("MIN_SIMILARITY", "0.30"))
    # 重排候选数：先召回 RERANK_TOP_K 个候选，再经 MMR 重排/去重后取 TOP_K 送入 LLM，
    # 候选更充分时重排质量更高（默认 10）。
    RERANK_TOP_K = int(os.environ.get("RERANK_TOP_K", "10"))
    # MMR（最大边际相关）权衡系数 lambda：1=纯相关性、0=纯多样性。
    # 取 0.6 兼顾"答得准"与"覆盖多个相关方面、避免同一段话重复出现"。
    MMR_LAMBDA = float(os.environ.get("MMR_LAMBDA", "0.6"))
    # 送入提示词的参考资料总长度上限（字符），防止上下文过长稀释注意力、产生冗长杂乱回答。
    MAX_CONTEXT_CHARS = int(os.environ.get("MAX_CONTEXT_CHARS", "2600"))
    # 单文档最多采用的切片数（重排后），避免一个文档霸占全部上下文。
    MAX_CHUNKS_PER_DOC = int(os.environ.get("MAX_CHUNKS_PER_DOC", "2"))
    # 检索提问指令前缀：bge-*-zh-v1.5 默认不加（官方推荐，实测分数更高）。
    # 若使用 bge-large-zh（非 v1.5）可设为：为这个句子生成表示以用于检索相关文章：
    QUERY_PREFIX = os.environ.get("QUERY_PREFIX", "")
    # 检索提问是否启用关键词扩展变体（多向量 max-pool）
    QUERY_EXPAND = os.environ.get("QUERY_EXPAND", "1")

    # ---- 上传 ----
    ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx"}
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024

    # ---- Redis 缓存（检索结果/会话缓存，降低重复向量计算与数据库压力）----
    # REDIS_ENABLE=0 时完全关闭缓存（含进程内兜底），不影响主流程。
    REDIS_ENABLE = os.environ.get("REDIS_ENABLE", "1")
    REDIS_HOST = os.environ.get("REDIS_HOST", "127.0.0.1")
    REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
    REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
    REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
    REDIS_TTL = int(os.environ.get("REDIS_TTL", "600"))  # 缓存过期秒数

    # ---- 跨域 ----
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # ---- 首启自动播种演示数据 ----
    AUTO_SEED = os.environ.get("AUTO_SEED", "1") == "1"
    # 知识库文档（疾病示例文档）是否随首启自动播种入库。
    # 默认 0：首启只播种用户/业务数据，知识库保持为空，由管理员/医生首次登录后清零并按需上传。
    # 设为 1：首启自动把 backend/data/uploads 下各疾病类别的示例文档向量化入库。
    SEED_KB_DOCS = os.environ.get("SEED_KB_DOCS", "0") == "1"
    print(f"API_KEY: {OPENAI_API_KEY[:8]}...{OPENAI_API_KEY[-4:] if OPENAI_API_KEY else ''}")
    print("EMBED_MODEL:", OPENAI_EMBED_MODEL)
    print("BASE_URL:", OPENAI_BASE_URL)
    # 注：实际向量库在首次请求时按可达性自动选择 Milvus / NumpyStore，此处仅提示首选
    print("VECTOR_STORE: Milvus(首选，不可用时自动降级 NumpyStore)")
