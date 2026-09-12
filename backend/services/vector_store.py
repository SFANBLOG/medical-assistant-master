"""
向量库（Vector Store）
==================================================================
- 优先使用 Milvus（集合 medical_chunks，kb_id 分区键 + cosine + HNSW 索引）；
- Milvus 未安装 / 未启动 / 连接失败时，自动降级为纯 Python 的 NumpyStore，
  同样返回 cosine 相似度，保证应用始终可用；
- 已取消 ChromaDB 方案（满足「需要改进的地方3.md」第 1 条）。
"""
import importlib.util
import json
import threading

import numpy as np

import config as cfg

_EMBED_DIM = int(cfg.EMBED_DIM)
_VECTORS_DIR = cfg.VECTORS_DIR
_VECTORS_DIR.mkdir(parents=True, exist_ok=True)

_HAS_PYMILVUS = importlib.util.find_spec("pymilvus") is not None


class NumpyStore:
    """纯 Python 向量索引（文件持久化）。"""
    def __init__(self):
        self._lock = threading.Lock()
        self._vecs = None
        self._meta = []
        self._vec_file = _VECTORS_DIR / "vectors.npy"
        self._meta_file = _VECTORS_DIR / "meta.json"
        self._load()

    def _load(self):
        if self._vec_file.exists():
            self._vecs = np.load(self._vec_file)
        else:
            self._vecs = np.zeros((0, _EMBED_DIM), dtype=np.float32)
        if self._meta_file.exists():
            try:
                self._meta = json.loads(self._meta_file.read_text(encoding="utf-8"))
            except Exception:
                self._meta = []
        else:
            self._meta = []
        if self._vecs.shape[1] != _EMBED_DIM and self._vecs.shape[0] > 0:
            print(f"[Store] 警告：已存向量维度 {self._vecs.shape[1]} 与 EMBED_DIM={_EMBED_DIM} 不一致，将重建索引。")
            self._vecs = np.zeros((0, _EMBED_DIM), dtype=np.float32)
            self._meta = []

    def _persist(self):
        np.save(self._vec_file, self._vecs)
        self._meta_file.write_text(json.dumps(self._meta, ensure_ascii=False), encoding="utf-8")

    def count(self):
        return len(self._meta)

    def clear(self):
        with self._lock:
            self._vecs = np.zeros((0, _EMBED_DIM), dtype=np.float32)
            self._meta = []
            self._persist()

    def add(self, chunks: list[dict]):
        """chunks: [{vector, doc_id, kb_id, chunk_index, visibility, title, text}]"""
        with self._lock:
            vecs = [np.asarray(c["vector"], dtype=np.float32).reshape(_EMBED_DIM) for c in chunks]
            if vecs:
                new = np.stack(vecs)
                self._vecs = np.vstack([self._vecs, new]) if self._vecs.shape[0] else new
            for c in chunks:
                self._meta.append({
                    "doc_id": c["doc_id"], "kb_id": c["kb_id"],
                    "chunk_index": c["chunk_index"], "visibility": c["visibility"],
                    "title": c.get("title", ""), "text": c.get("text", ""),
                })
            self._persist()

    def search(self, query_vec, k=10):
        """返回按 cosine 降序的候选列表（含 meta 与 similarity）。"""
        q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
        n = q.shape[0]
        if self._vecs.shape[1] != n and self._vecs.shape[0] > 0:
            self.clear()
            return []
        if self._vecs.shape[0] == 0:
            return []
        sims = self._vecs @ q  # 余弦 = 点积（向量已归一化）
        idx = np.argsort(-sims)[:k]
        out = []
        for i in idx:
            out.append({"similarity": float(sims[i]), **self._meta[int(i)]})
        return out


class MilvusStore:
    """Milvus 向量库（可选，需安装 pymilvus 且服务可达）。"""
    def __init__(self):
        from pymilvus import (Collection, CollectionSchema, FieldSchema, DataType,
                              connections, utility)
        self._connections = connections
        self._utility = utility
        self._Collection = Collection
        self._coll_name = cfg.MILVUS_COLLECTION
        self._dim = _EMBED_DIM
        connections.connect(alias="default",
                            host=cfg.MILVUS_HOST, port=cfg.MILVUS_PORT, timeout=5)
        if not utility.has_collection(self._coll_name):
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="kb_id", dtype=DataType.INT64),
                FieldSchema(name="doc_id", dtype=DataType.INT64),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="visibility", dtype=DataType.VARCHAR, max_length=16),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self._dim),
            ]
            schema = CollectionSchema(fields, description="medical chunks")
            self._coll = Collection(self._coll_name, schema, partition_key_field="kb_id")
            self._coll.create_index("embedding", {
                "index_type": "HNSW", "metric_type": "COSINE",
                "params": {"M": 8, "efConstruction": 200}})
        else:
            self._coll = Collection(self._coll_name)
        self._coll.load()

    def count(self):
        return self._coll.num_entities

    def clear(self):
        self._coll.delete(expr="kb_id >= 0")

    def add(self, chunks: list[dict]):
        if not chunks:
            return
        data = [
            [c["kb_id"] for c in chunks],
            [c["doc_id"] for c in chunks],
            [c["chunk_index"] for c in chunks],
            [c["visibility"] for c in chunks],
            [(c.get("title") or "")[:512] for c in chunks],
            [(c.get("text") or "")[:65535] for c in chunks],
            [np.asarray(c["vector"], dtype=np.float32).reshape(-1).tolist() for c in chunks],
        ]
        self._coll.insert(data)
        self._coll.flush()

    def search(self, query_vec, k=10, visibility_filter=None):
        expr = None
        if visibility_filter:
            vs = ",".join("'" + v + "'" for v in visibility_filter)
            expr = f"visibility in [{vs}]"
        res = self._coll.search(
            data=[np.asarray(query_vec, dtype=np.float32).reshape(-1).tolist()],
            anns_field="embedding", param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=k, expr=expr,
            output_fields=["doc_id", "kb_id", "chunk_index", "visibility", "title", "text"],
        )
        out = []
        for hits in res:
            for h in hits:
                out.append({
                    "similarity": float(h.score), "doc_id": h.entity.get("doc_id"),
                    "kb_id": h.entity.get("kb_id"), "chunk_index": h.entity.get("chunk_index"),
                    "visibility": h.entity.get("visibility"), "title": h.entity.get("title"),
                    "text": h.entity.get("text"),
                })
        return out


# ---------------------------------------------------------------------------
# 工厂：优先 Milvus，失败回退 NumpyStore
# ---------------------------------------------------------------------------
_STORE = None
_STORE_TYPE = None


def get_vector_store():
    global _STORE, _STORE_TYPE
    if _STORE is not None:
        return _STORE
    if cfg.MILVUS_ENABLE and _HAS_PYMILVUS:
        try:
            _STORE = MilvusStore()
            _STORE_TYPE = "milvus"
            print("[Store] 已连接 Milvus 向量库。")
            return _STORE
        except Exception as e:  # noqa
            print(f"[Store] Milvus 不可用，回退 NumpyStore：{e}")
    _STORE = NumpyStore()
    _STORE_TYPE = "numpy"
    print(f"[Store] 使用 NumpyStore 兜底（已索引 {_STORE.count()} 个片段）。")
    return _STORE
