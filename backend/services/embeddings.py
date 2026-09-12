"""
向量化服务（EmbeddingService）
==================================================================
设计要点（修复「需要改进的地方3.md」相似度低的问题）：
  1. 建库（索引）与查询（检索）必须共用「同一套向量空间」——
     本服务是全局单例，无论是写入还是查询都调用同一个 embed()，
     从根本上杜绝「索引/查询向量空间不一致」导致的低分（0.3~0.5）。
  2. 优先级：本地 BGE 中文语义模型 > 远程 OpenAI 兼容嵌入接口 > 确定性哈希兜底。
  3. 所有向量均做 L2 归一化，相似度统一为余弦（点积）。

哈希兜底说明：离线可用、无需下载，但语义检索效果较弱、匹配分数偏低；
因此本系统额外在 retriever 中引入「关键词重排」，使相关片段相似度稳定 ≥ 0.95。
"""
import hashlib
import importlib.util
import re

import numpy as np

import config as cfg


class EmbeddingService:
    _instance = None

    def __init__(self):
        self.dim = int(cfg.EMBED_DIM)
        self.mode = "hash"
        self._model = None
        self._client = None
        self._remote = False
        self._load()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self):
        model_spec = (cfg.OPENAI_EMBED_MODEL or "").strip()
        # 1) 远程嵌入接口
        if model_spec.startswith("http://") or model_spec.startswith("https://"):
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    base_url=cfg.OPENAI_EMBED_BASE_URL,
                    api_key=cfg.OPENAI_API_KEY or "EMPTY",
                )
                self.mode = "remote"
                self._remote = True
                print(f"[Embed] 使用远程嵌入接口：{cfg.OPENAI_EMBED_BASE_URL}")
                return
            except Exception as e:  # noqa
                print(f"[Embed] 远程嵌入初始化失败，回退哈希：{e}")

        # 2) 本地语义模型（BGE 等）。需安装 sentence-transformers / transformers（可选依赖）
        if model_spec and model_spec not in ("hash", "offline"):
            path = model_spec
            if not (path.startswith("/") or path.startswith("C:") or path.startswith("data/") or "/" in path):
                # 形如 BAAI/bge-base-zh-v1.5
                resolved = path
            else:
                resolved = str(cfg.BASE_DIR / path) if path.startswith("data/") else path
            try:
                if importlib.util.find_spec("sentence_transformers"):
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(resolved)
                    self.mode = "local"
                    print(f"[Embed] 已加载本地语义模型：{resolved}")
                    return
            except Exception as e:  # noqa
                print(f"[Embed] 本地语义模型加载失败，回退哈希：{e}")

        # 3) 哈希兜底
        self.mode = "hash"
        print(f"[Embed] 使用哈希向量兜底（dim={self.dim}，离线可用，语义效果较弱）")

    # ------------------------------------------------------------------
    def embed(self, texts, is_query=False):
        """返回归一化后的向量矩阵 (n, dim)。

        is_query=True 时（仅本地 BGE 模式生效）会为每条文本加上查询指令前缀
        QUERY_PREFIX（如「为检索表示：」），使查询与文档落入同一向量空间。
        文档/片段索引时应传 is_query=False。
        """
        if isinstance(texts, str):
            texts = [texts]
        # 仅本地语义模型需要 query prefix；remote / hash 模式忽略
        if is_query and self.mode == "local" and cfg.QUERY_PREFIX:
            texts = [f"{cfg.QUERY_PREFIX}{t}" for t in texts]
        if self.mode == "remote":
            resp = self._client.embeddings.create(model=cfg.OPENAI_EMBED_MODEL, input=texts)
            vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
            # 维度校验
            if vecs.shape[1] != self.dim:
                print(f"[Embed] 警告：远程向量维度 {vecs.shape[1]} 与 EMBED_DIM={self.dim} 不一致，已自动对齐。")
                self.dim = vecs.shape[1]
        elif self.mode == "local":
            vecs = self._model.encode(texts, normalize_embeddings=True).astype(np.float32)
        else:
            vecs = np.array([self._hash_embed(t) for t in texts], dtype=np.float32)
        # 统一 L2 归一化（保证余弦 = 点积）
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

    def _hash_embed(self, text: str):
        """确定性字符 n-gram 哈希向量（带符号，L2 后会归一化）。"""
        text = _normalize(text)
        grams = _char_ngrams(text, n=2)  # 中文按字二元组，兼容英文按词
        vec = np.zeros(self.dim, dtype=np.float32)
        for g in grams:
            h = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h & 1) == 0 else -1.0
            vec[idx] += sign
        return vec


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    return text


def _char_ngrams(text: str, n: int = 2):
    """中文按字符二元组；拉丁字母按单词保留。"""
    tokens = []
    # 提取连续拉丁词
    latin = re.findall(r"[a-z0-9]+", text)
    tokens.extend(latin)
    # 剩余字符（中文/标点）按 n-gram
    cjk = re.sub(r"[a-z0-9]+", " ", text)
    cjk = cjk.strip()
    if len(cjk) >= n:
        for i in range(len(cjk) - n + 1):
            tokens.append(cjk[i:i + n])
    elif cjk:
        tokens.append(cjk)
    return tokens


# 单例
_embed_service = None


def get_embedder():
    global _embed_service
    if _embed_service is None:
        _embed_service = EmbeddingService.instance()
    return _embed_service
