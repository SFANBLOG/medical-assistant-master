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
import socket
import threading
from typing import Optional

from services.llm import LLMProvider, OfflineFallbackLLM, OpenAICompatLLM
from services.vector_store import MilvusStore, MilvusUnavailable, NumpyStore

logger = logging.getLogger(__name__)


def _milvus_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    """在真正实例化 MilvusClient 之前做一次轻量 TCP 探活。

    - 端口未监听（如本地未启动 docker、或未部署 Milvus）-> 直接返回 False，
      避免构造 MilvusClient 时抛出 <MilvusException> 之类的原始异常污染控制台。
    - 仅当端口确实可达时才尝试连接，保证本地开发零噪音、Docker 内部正常走 Milvus。
    """
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False

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
            host = cfg.get("MILVUS_HOST", "127.0.0.1")
            port = int(cfg.get("MILVUS_PORT", "19530"))
            # 先轻量探活：端口不可达（本地未启动 docker / 未部署 Milvus）时，
            # 直接静默降级，不打印任何异常，控制台保持干净。
            if _milvus_reachable(host, port):
                try:
                    _store = MilvusStore(
                        host=host,
                        port=port,
                        dim=cfg["EMBED_DIM"],
                        db_name=cfg.get("MILVUS_DB", "default"),
                        collection=cfg.get("MILVUS_COLLECTION"),
                        min_similarity=float(cfg.get("MIN_SIMILARITY", "0.3")),
                    )
                    logger.info("向量存储：Milvus（MilvusStore）")
                    return _store
                except MilvusUnavailable:
                    # 端口可达但握手/鉴权失败：降级一次并给出友好提示，不暴露原始异常
                    logger.warning(
                        "Milvus 已可达但初始化失败，已降级到本地 NumpyStore（请检查 Milvus 版本/集合维度）"
                    )
                except Exception as exc:  # noqa: BLE001 其它初始化异常统一兜底
                    logger.warning("Milvus 初始化异常，已降级到本地 NumpyStore：%s", type(exc).__name__)
            else:
                logger.info(
                    "未检测到 Milvus 服务（%s:%s），已自动降级到本地 NumpyStore（本地开发模式，向量持久化于 VECTOR_DIR）",
                    host, port,
                )

        # 2) 纯 Python 兜底
        _store = NumpyStore(
            vector_dir,
            cfg["EMBED_DIM"],
            min_similarity=float(cfg.get("MIN_SIMILARITY", "0.3")),
        )
        logger.info("向量存储：NumpyStore（纯 Python 兜底）")
        return _store
