"""
全局配置加载：从 .env 文件读取，不覆盖已存在的环境变量。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（backend/ 的父目录 或 backend/ 自身）
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent

# 在 load_dotenv 之前快照「进程真实环境变量」。
# 部署平台（PocketBay 等）注入的变量只存在于真实环境，必须先抓取，
# 否则会被 .env 合并进 os.environ 后无法区分来源，导致面板配置被静默忽略。
_ENV_SNAPSHOT = dict(os.environ)

# 加载 .env（优先 backend/.env，其次 项目根/.env）
_env_backend = BACKEND_DIR / ".env"
_env_root = PROJECT_DIR / ".env"
if _env_backend.exists():
    load_dotenv(_env_backend, override=False)
if _env_root.exists():
    load_dotenv(_env_root, override=False)

# ---- 数据库 ----
DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
DATABASE_NAME = os.getenv("DATABASE_NAME", "medical-assistant")
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "123456")

# ---- 向量库（Milvus）----
MILVUS_ENABLE = os.getenv("MILVUS_ENABLE", "0") == "1"
MILVUS_HOST = os.getenv("MILVUS_HOST", "127.0.0.1")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
# 连接超时（秒）：本地未启动 Milvus 时快速失败并降级，避免阻塞启动。
MILVUS_CONNECT_TIMEOUT = int(os.getenv("MILVUS_CONNECT_TIMEOUT", "3"))

# ---- 聊天 / 向量化 ----
# 同时兼容两套命名：LLM_*（本项目 canonical）与 OPENAI_*（历史命名）。
#
# 前缀决策优先级（绝不跨前缀混搭 base_url 与 api_key）：
#   1) 真实环境变量里存在「成对齐全」的 LLM_* / OPENAI_*  → 采用（平台面板覆盖生效）
#   2) 否则用合并 .env 后「成对齐全」的一套                 → 采用（打包进镜像的配置）
#   3) 再退到「只填了半套」的真实环境变量                   → 采用
#   4) 都没有 → 默认 LLM_
#
# 历史事故：面板里只新填了 key、没填 BASE_URL，结果「新 key 打到 .env 里的旧网关」
# → 必然 401 authentication_error。把「半套」排在「完整对」之后，
# 可以保证残缺的覆盖不会破坏 .env 里已配套的网关配置。


def _complete_prefix(env: dict) -> str:
    """返回「BASE_URL + API_KEY 成对齐全」的前缀，没有则返回空串。"""
    for prefix in ("LLM_", "OPENAI_"):
        if env.get(prefix + "BASE_URL") and env.get(prefix + "API_KEY"):
            return prefix
    return ""


def _any_prefix(env: dict) -> str:
    """返回「至少填了一项」的前缀，没有则返回空串。"""
    for prefix in ("LLM_", "OPENAI_"):
        if env.get(prefix + "BASE_URL") or env.get(prefix + "API_KEY"):
            return prefix
    return ""


LLM_CONFIG_SOURCE = "env" if _complete_prefix(_ENV_SNAPSHOT) else "dotenv"
_LLM_PREFIX = (
    _complete_prefix(_ENV_SNAPSHOT)     # ① 平台完整覆盖
    or _complete_prefix(os.environ)     # ② .env 文件完整配置
    or _any_prefix(_ENV_SNAPSHOT)       # ③ 平台半套覆盖（聊胜于无）
    or _any_prefix(os.environ)          # ④ .env 半套
    or "LLM_"                           # ⑤ 兜底默认
)

LLM_BASE_URL = os.getenv(_LLM_PREFIX + "BASE_URL") or "https://api.deepseek.com/v1"
LLM_API_KEY = os.getenv(_LLM_PREFIX + "API_KEY") or ""
# 模型名支持三套命名，按优先级：LLM_MODEL > LLM_CHAT_MODEL > OPENAI_CHAT_MODEL
# （LLM_MODEL 是「单一主力模型」的简写命名，LLM_MODEL_MINOR/MAJOR 目前仅记录不启用）
LLM_CHAT_MODEL = (
    os.getenv("LLM_MODEL")
    or os.getenv(_LLM_PREFIX + "CHAT_MODEL")
    or "deepseek-chat"
)
LLM_MODEL_MINOR = os.getenv("LLM_MODEL_MINOR", "")
LLM_MODEL_MAJOR = os.getenv("LLM_MODEL_MAJOR", "")

# 历史别名（向后兼容既有代码 import）
OPENAI_BASE_URL = LLM_BASE_URL
OPENAI_API_KEY = LLM_API_KEY
OPENAI_CHAT_MODEL = LLM_CHAT_MODEL
def _resolve_embed_model() -> str:
    """
    确定嵌入模型配置。

    嵌入模型只接受三类合法值：
      - "auto"：自动检测 MODEL_DIR 下已下载的 BGE 模型
      - 含 "/" 的 HuggingFace repo_id 或本地路径（如 BAAI/bge-base-zh-v1.5）
      - 已知嵌入模型关键字（bge / gte / e5 / embedding 等）

    为什么要校验：聊天模型名（如 deepseek-v4-flash）一旦被误配到嵌入位，
    embedder 会找不到本地模型并**静默回退 HashEmbedder（无语义能力）**，
    导致此前用 BGE 建立的语义索引整体失效，且日志里只有一行提示，极难排查。
    因此凡是不像嵌入模型的值一律丢弃，回退 "auto"，并在启动时打印告警。
    """
    candidates = [
        ("LLM_MODEL_EMBEDDING", os.getenv("LLM_MODEL_EMBEDDING")),
        ("LLM_EMBED_MODEL", os.getenv("LLM_EMBED_MODEL")),
        ("OPENAI_EMBED_MODEL", os.getenv("OPENAI_EMBED_MODEL")),
    ]
    embed_kw = ("bge", "gte", "e5", "embedding", "embed", "sentence")
    for name, val in candidates:
        if not val:
            continue
        v = val.strip()
        low = v.lower()
        if v == "auto" or "/" in v or "\\" in v or any(k in low for k in embed_kw):
            return v
        print(
            f"[config] 忽略 {name}={v}：它不像嵌入模型标识，"
            f"强制回退 auto（避免退化成无语义的 HashEmbedder）"
        )
    return "auto"


OPENAI_EMBED_MODEL = _resolve_embed_model()

# 单次补全预算。推理型模型（deepseek-v4-flash 等）的思考过程同样计入 token，
# 预算过小会出现「只思考、不回答」，所以默认给足。
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "180"))
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
# 重排融合权重（稠密余弦 + BM25 归一化 + 词法重叠）——仅 HYBRID_FUSION=weighted 时生效
RERANK_W_DENSE = float(os.getenv("RERANK_W_DENSE", "0.55"))
RERANK_W_BM25 = float(os.getenv("RERANK_W_BM25", "0.30"))
RERANK_W_LEXICAL = float(os.getenv("RERANK_W_LEXICAL", "0.15"))
# 混合检索融合方式（二选一）：
#   weighted（默认）：双分支合并去重 → 加权证据分 + 实体地板校准 + 位置/长度惩罚的重排器
#   rrf            ：双分支各按名次做 Reciprocal Rank Fusion（Σ 1/(RRF_K+rank)）取 Top-K，
#                    纯排名融合、丢弃分数幅值，不经过加权重排器。
# 默认保持 weighted 以维持已调优的相关度与离线指标；设 HYBRID_FUSION=rrf 可启用 RRF 通道。
HYBRID_FUSION = os.getenv("HYBRID_FUSION", "weighted").lower()
# RRF 平滑常数（标准取值 60），名次越靠后贡献越小。
RRF_K = int(os.getenv("RRF_K", "60"))
# Cross-Encoder 模型路径（留空或 "auto" 则用融合模式；推荐 BAAI/bge-reranker-v2-min）
RERANK_MODEL_PATH = os.getenv("RERANK_MODEL_PATH", "auto")
# 值 "auto" 表示自动在 MODEL_DIR 下搜索已下载的 CE 模型，找不到则用增强融合。
# 是否启用 Cross-Encoder 作为增强信号（默认关闭）：
#   - bge-reranker-* 类模型在 CPU 上单查询需 14~31s，且原始 sigmoid 分数被压缩在
#     0.5~0.73 区间、对"非常相关/较相关"区分度差，直接替换融合反而会让展示相关度
#     从 95%+ 掉到 ~73%。故默认关闭，仅作可选增强（与融合取 max，只升不降）。
#   - 设为 true 且模型存在时，CE 仅作为"增强boost"，绝不拉低融合给出高分的相关文档。
RERANK_USE_CE = os.getenv("RERANK_USE_CE", "false").lower() in ("1", "true", "yes", "on")

# ---- 服务端口 ----
# 优先读平台注入的 PORT（PocketBay 等平台约定），回退 BACKEND_PORT / 默认 8010
BACKEND_PORT = int(os.getenv("PORT", os.getenv("BACKEND_PORT", "8010")))

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
# 兼容旧命名 JWT_EXPIRES_HOURS（.env.example 里曾用过）
JWT_EXP_HOURS = int(os.getenv("JWT_EXP_HOURS") or os.getenv("JWT_EXPIRES_HOURS") or "24")

# ---- 路径 ----
DATA_DIR = BACKEND_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
MODEL_DIR = DATA_DIR / "ai_models"
SQLITE_PATH = DATA_DIR / f"{DATABASE_NAME}.db"

# 确保目录存在
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ---- Milvus 集合名 ----
MILVUS_COLLECTION = "medical_chunks"
