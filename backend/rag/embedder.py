"""
向量化模型：支持两种模式（按优先级自动选择）。

1. BGE 本地模型（OPENAI_EMBED_MODEL 指向本地路径或 HF id）
2. 内置确定性哈希向量（离线可用，维度 EMBED_DIM，语义效果差但零配置）

哈希向量原理：对每个 token 取 hash，映射到固定维度向量并做 L2 归一化。
相同/相似文本的 token 分布接近 → cosine 相似度高。
"""
import hashlib
import re

import numpy as np

from backend import config

# ---- 模块级缓存 ----
_bge_model = None
_bge_failed = False


class HashEmbedder:
    """确定性哈希向量嵌入器。"""

    def __init__(self, dim: int = None):
        self._dim = dim or config.EMBED_DIM

    def _tokenize(self, text: str) -> list[str]:
        """简易中文分词：按单字 + bigram + 英文单词。"""
        tokens = []
        for m in re.findall(r"[a-zA-Z]+", text):
            tokens.append(m.lower())
        chinese = re.findall(r"[\u4e00-\u9fff]+", text)
        for seg in chinese:
            for i in range(len(seg)):
                tokens.append(seg[i])
            for i in range(len(seg) - 1):
                tokens.append(seg[i:i + 2])
        return tokens

    def embed(self, text: str) -> np.ndarray:
        """将文本编码为 L2 归一化的 float32 向量。"""
        vec = np.zeros(self._dim, dtype=np.float32)
        tokens = self._tokenize(text)
        if not tokens:
            return vec
        for token in tokens:
            h = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(h[:8], 16) % self._dim
            sign = 1.0 if int(h[8], 16) % 2 == 0 else -1.0
            vec[idx] += sign * (1.0 + len(token) * 0.1)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        return [self.embed(t) for t in texts]

    @property
    def dim(self) -> int:
        return self._dim


def _try_bge_model():
    """尝试加载 BGE 本地模型。"""
    global _bge_model, _bge_failed
    if _bge_failed or _bge_model is not None:
        return _bge_model

    model_path = config.OPENAI_EMBED_MODEL
    if not model_path:
        _bge_failed = True
        return None

    try:
        from sentence_transformers import SentenceTransformer
        _bge_model = SentenceTransformer(model_path)
        print(f"[Embedder] BGE 模型加载成功: {model_path}, "
              f"dim={_bge_model.get_sentence_embedding_dimension()}")
        return _bge_model
    except ImportError:
        print("[Embedder] sentence_transformers 未安装，回退到哈希向量")
        _bge_failed = True
        return None
    except Exception as e:
        print(f"[Embedder] BGE 模型加载失败: {e}，回退到哈希向量")
        _bge_failed = True
        return None


class _BGEEmbedder:
    """BGE 模型包装器，接口与 HashEmbedder 一致。"""

    def __init__(self, model):
        self._model = model
        self._dim = model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> np.ndarray:
        vec = self._model.encode(text, normalize_embeddings=True)
        return np.array(vec, dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return [np.array(v, dtype=np.float32) for v in vecs]

    @property
    def dim(self) -> int:
        return self._dim


def get_embedder():
    """
    获取嵌入器实例。

    优先级：
    1. BGE 本地模型（如果配置了 OPENAI_EMBED_MODEL 且可加载）
    2. 哈希向量（兜底，零配置）
    """
    bge = _try_bge_model()
    if bge is not None:
        return _BGEEmbedder(bge)
    return HashEmbedder()
