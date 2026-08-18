"""应用级单例：向量存储选择 + LLM 提供者选择。"""
import threading
from typing import Optional

# chromadb 在部分平台（无 MSVC 编译工具的 Windows）无法安装，此处可选导入，
# 不可用时自动降级为纯 Python 的 NumpyStore（见 get_vector_store）。
try:
    import chromadb
except ImportError:  # pragma: no cover
    chromadb = None

from services.llm import LLMProvider, OfflineFallbackLLM, OpenAICompatLLM

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

    优先使用 ChromaDB（Linux/Docker 下可正常安装）；在缺少 MSVC 编译工具、
    无法安装 chromadb 的平台上（部分 Windows），自动降级为纯 Python 的
    NumpyStore，二者接口一致。
    """
    global _store
    with _store_lock:
        if _store is None:
            try:
                import chromadb  # noqa: F401

                _store = ChromaStore(cfg["CHROMA_DIR"])
            except ImportError:
                from services.vector_store import NumpyStore

                _store = NumpyStore(cfg["CHROMA_DIR"], cfg["EMBED_DIM"])
        return _store


class ChromaStore:
    def __init__(self, persist_directory="./chroma_db"):
        # 确保使用正确的初始化方式
        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collections = {}
        self._lock = threading.Lock()
        self._batch = 512

    def _col(self, kb_id):
        if kb_id not in self._collections:
            # 获取或创建集合
            self._collections[kb_id] = self._client.get_or_create_collection(
                name=f"kb_{kb_id}",
                metadata={"hnsw:space": "cosine"}
            )
        return self._collections[kb_id]

    # ... 其他方法
    def upsert(self, kb_id: int, ids, embeddings, documents, metadatas) -> None:
        with self._lock:
            col = self._col(kb_id)
            for i in range(0, len(ids), self._batch):
                col.upsert(
                    ids=ids[i: i + self._batch],
                    embeddings=embeddings[i: i + self._batch],
                    documents=documents[i: i + self._batch],
                    metadatas=metadatas[i: i + self._batch],
                )

    def query(self, kb_id: int, embedding: list[float], top_k: int = 5) -> list[dict]:
        with self._lock:
            col = self._col(kb_id)
            count = col.count()
            if count == 0:
                return []
            try:
                res = col.query(
                    query_embeddings=[embedding],
                    n_results=min(top_k, count),
                    include=["documents", "metadatas", "distances"],
                )
            except ValueError:
                # 集合为空或请求数超量时 Chroma 会抛错，安全返回空
                return []
        hits = []
        for i in range(len(res["ids"][0])):
            hits.append(
                {
                    "id": res["ids"][0][i],
                    "text": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i],
                    "distance": float(res["distances"][0][i]),
                }
            )
        return hits

    def delete_doc(self, kb_id: int, doc_id: int) -> None:
        with self._lock:
            col = self._col(kb_id)
            col.delete(where={"doc_id": doc_id})

    def delete_collection(self, kb_id: int) -> None:
        with self._lock:
            self._client.delete_collection(f"kb_{kb_id}")
