"""应用级单例：向量存储选择 + LLM 提供者选择。

向量存储：
- 首选 Milvus（MILVUS_ENABLE=1，向量库由 services.vector_store.MilvusStore 实现，
  集合设计见该模块）。Milvus 未启动 / 未安装 pymilvus 时，自动降级为纯 Python 的
  NumpyStore（同样返回 cosine 相似度），保证应用始终可用。
- 已取消 ChromaDB 存储模式（不再依赖 chromadb）。

LLM 提供者：
- 配置了 OPENAI_BASE_URL + OPENAI_API_KEY -> OpenAICompatLLM（含本地 embedding 模型）；
- 否则 -> OfflineFallbackLLM（确定性哈希向量 + 摘要式回答）。
"""
import logging
import threading
from typing import Optional

from services.llm import LLMProvider, OfflineFallbackLLM, OpenAICompatLLM
from services.vector_store import MilvusStore, MilvusUnavailable, NumpyStore

logger = logging.getLogger(__name__)

_llm: Optional[LLMProvider] = None
_llm_lock = threading.Lock()
_store = None
_store_lock = threading.Lock()


def get_llm(cfg) -> LLMProvider:
    global _llm
    with _llm_lock:
        if _llm is None:
            if cfg["OPENAI_BASE_URL"] and cfg["OPENAI_API_KEY"]:
                _llm = OpenAICompatLLM(cfg)
            else:
                _llm = OfflineFallbackLLM(cfg)
        return _llm


def get_vector_store(cfg):
    """返回向量存储实例（进程内缓存）。

    优先 Milvus；Milvus 不可用时降级 NumpyStore（接口与返回值语义一致）。
    """
    global _store
    with _store_lock:
        if _store is not None:
            return _store

        vector_dir = cfg.get("VECTOR_DIR") or cfg.get("CHROMA_DIR")

        # 1) Milvus（用户首选）
        if cfg.get("MILVUS_ENABLE", "1") not in ("0", "false", "False"):
            try:
                _store = MilvusStore(
                    host=cfg.get("MILVUS_HOST", "127.0.0.1"),
                    port=int(cfg.get("MILVUS_PORT", "19530")),
                    dim=cfg["EMBED_DIM"],
                    db_name=cfg.get("MILVUS_DB", "default"),
                    collection=cfg.get("MILVUS_COLLECTION"),
                    min_similarity=float(cfg.get("MIN_SIMILARITY", "0.3")),
                )
                logger.info("向量存储：Milvus（MilvusStore）")
                return _store
            except MilvusUnavailable as e:
                logger.warning(f"Milvus 不可用，降级 NumpyStore：{e}")

        # 2) 纯 Python 兜底
        _store = NumpyStore(
            vector_dir,
            cfg["EMBED_DIM"],
            min_similarity=float(cfg.get("MIN_SIMILARITY", "0.3")),
        )
        logger.info("向量存储：NumpyStore（纯 Python 兜底）")
        return _store
