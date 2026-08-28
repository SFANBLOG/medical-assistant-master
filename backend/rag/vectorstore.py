"""
向量存储：Milvus 主方案 + NumpyStore 纯 Python 兜底。

- Milvus 集合 `medical_chunks`：字段 (id, kb_id, doc_id, chunk_index, text, embedding)
  cosine 度量 + HNSW 索引 + kb_id 分区键
- NumpyStore：内存 dict + numpy 数组，cosine 相似度，功能等价；
  数据自动持久化到 backend/data/numpy_store.pkl（进程重启后仍可检索）
"""
import json
import pickle
import threading
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from pickle import Unpickler

from backend import config
from backend.rag.embedder import get_embedder

# 兼容旧版打包路径：重构前向量记录以 `rag.*` 等顶层包名序列化，
# 重构后统一为 `backend.*`，反序列化时做一次性路径映射。
_OLD_TOP_PKGS = ("rag", "utils", "services", "routes", "models", "seed", "config")


class _CompatUnpickler(Unpickler):
    def find_class(self, module: str, name: str):
        for pkg in _OLD_TOP_PKGS:
            if module == pkg or module.startswith(pkg + "."):
                module = "backend." + module
                break
        return super().find_class(module, name)


@dataclass
class VectorRecord:
    """一条向量记录。"""
    id: str
    kb_id: int
    doc_id: int
    chunk_index: int
    text: str
    embedding: list = field(default_factory=list)


class NumpyStore:
    """纯 Python + numpy 的向量存储兜底方案。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: dict[str, VectorRecord] = {}  # id -> record
        self._matrix: Optional[np.ndarray] = None    # (N, D) float32
        self._ids: list[str] = []                     # 与矩阵行对齐
        self._dirty = True                            # 矩阵是否需要重建
        self._dim = None
        self._embedder = get_embedder()
        self._dim = self._embedder.dim
        # 持久化路径：进程重启后从磁盘恢复向量
        self._persist_path = config.DATA_DIR / "numpy_store.pkl"
        self._load_from_disk()

    def _load_from_disk(self):
        """启动时从磁盘加载向量数据。

        使用兼容反序列化器，可正确加载重构前（模块路径为 `rag.*` 等）保存的 pickle，
        并在加载后重新落盘一次，将记录迁移到新的 `backend.*` 模块路径。
        """
        try:
            if self._persist_path.exists() and self._persist_path.stat().st_size > 0:
                with open(self._persist_path, "rb") as f:
                    self._records = _CompatUnpickler(f).load()
                if not isinstance(self._records, dict):
                    self._records = {}
                self._dirty = True
                print(f"[NumpyStore] 从磁盘加载 {len(self._records)} 条向量记录")
                # 首次以新模块路径重新落盘，完成 pickle 迁移
                if self._records:
                    self._save_to_disk()
        except Exception as e:
            print(f"[NumpyStore] 加载持久化数据失败（忽略）: {e}")
            self._records = {}

    def _save_to_disk(self):
        """将向量数据持久化到磁盘（临时文件 + 原子替换）。"""
        try:
            tmp = self._persist_path.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                pickle.dump(self._records, f)
            tmp.replace(self._persist_path)
        except Exception as e:
            print(f"[NumpyStore] 持久化失败: {e}")

    def _rebuild_matrix(self):
        """重建矩阵（增删后调用）。"""
        if not self._records:
            self._matrix = None
            self._ids = []
            return
        self._ids = list(self._records.keys())
        self._matrix = np.array(
            [np.asarray(self._records[i].embedding, dtype=np.float32) for i in self._ids],
            dtype=np.float32,
        )

    def insert(self, record: VectorRecord):
        """插入一条记录。"""
        with self._lock:
            self._records[record.id] = record
            self._dirty = True
        self._save_to_disk()

    def insert_batch(self, records: list[VectorRecord]):
        """批量插入。"""
        with self._lock:
            for r in records:
                self._records[r.id] = r
            self._dirty = True
        self._save_to_disk()

    def delete_by_doc(self, doc_id: int):
        """按文档 ID 删除所有 chunk。"""
        with self._lock:
            to_del = [k for k, v in self._records.items() if v.doc_id == doc_id]
            for k in to_del:
                del self._records[k]
            self._dirty = True
        self._save_to_disk()

    def delete_by_kb(self, kb_id: int):
        """按知识库 ID 删除所有 chunk。"""
        with self._lock:
            to_del = [k for k, v in self._records.items() if v.kb_id == kb_id]
            for k in to_del:
                del self._records[k]
            self._dirty = True
        self._save_to_disk()

    def search(
        self,
        query_vec: np.ndarray,
        kb_ids: list[int],
        top_k: int = config.TOP_K,
        min_similarity: float = config.MIN_SIMILARITY,
    ) -> list[dict]:
        """
        检索最相似的 top_k 条记录。

        返回: [{"id", "kb_id", "doc_id", "chunk_index", "text", "similarity"}]
        """
        with self._lock:
            if self._dirty:
                self._rebuild_matrix()
                self._dirty = False
            if self._matrix is None or len(self._ids) == 0:
                return []

            # 先按 kb_id 过滤
            if kb_ids:
                mask = np.array(
                    [self._records[i].kb_id in kb_ids for i in self._ids],
                    dtype=bool,
                )
                if not mask.any():
                    return []
                sub_matrix = self._matrix[mask]
                sub_ids = [self._ids[i] for i, m in enumerate(mask) if m]
            else:
                sub_matrix = self._matrix
                sub_ids = self._ids

            # cosine 相似度（向量已 L2 归一化 → 等价于点积）
            sims = sub_matrix @ query_vec

            # 取 top_k
            k = min(top_k, len(sims))
            top_idx = np.argpartition(sims, -k)[-k:]
            top_idx = top_idx[np.argsort(sims[top_idx])[::-1]]

            results = []
            for idx in top_idx:
                sim = float(sims[idx])
                if sim < min_similarity:
                    continue
                rec = self._records[sub_ids[idx]]
                results.append({
                    "id": rec.id,
                    "kb_id": rec.kb_id,
                    "doc_id": rec.doc_id,
                    "chunk_index": rec.chunk_index,
                    "text": rec.text,
                    "similarity": sim,
                })
            return results

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def get_all_chunks(self) -> list[dict]:
        """
        导出全部 chunk（供 BM25 等稀疏检索器构建索引）。

        返回: [{"id","kb_id","doc_id","chunk_index","text"}, ...]
        """
        with self._lock:
            if self._dirty:
                self._rebuild_matrix()
                self._dirty = False
            return [
                {
                    "id": rec.id,
                    "kb_id": rec.kb_id,
                    "doc_id": rec.doc_id,
                    "chunk_index": rec.chunk_index,
                    "text": rec.text,
                }
                for rec in self._records.values()
            ]

    def clear(self) -> None:
        """清空全部向量（重建索引前调用）。"""
        with self._lock:
            self._records = {}
            self._matrix = None
            self._ids = []
            self._dirty = True
            self._save_to_disk()


class MilvusStore:
    """Milvus 向量存储。"""

    def __init__(self):
        from pymilvus import connections, Collection, utility, FieldSchema, CollectionSchema, DataType
        self._connections = connections
        self._Collection = Collection
        self._utility = utility
        self._FieldSchema = FieldSchema
        self._CollectionSchema = CollectionSchema
        self._DataType = DataType

        self._connected = False
        self._collection = None
        self._embedder = get_embedder()
        self._dim = self._embedder.dim

    def _connect(self) -> bool:
        """连接 Milvus，成功返回 True。"""
        if self._connected:
            return True
        try:
            self._connections.connect(
                alias="default",
                host=config.MILVUS_HOST,
                port=str(config.MILVUS_PORT),
                timeout=5,
            )
            self._connected = True
            print(f"[Milvus] 连接成功: {config.MILVUS_HOST}:{config.MILVUS_PORT}")
            self._ensure_collection()
            return True
        except Exception as e:
            print(f"[Milvus] 连接失败: {e}")
            self._connected = False
            return False

    def _ensure_collection(self):
        """确保集合存在，不存在则创建。"""
        if not self._connected:
            return

        coll_name = config.MILVUS_COLLECTION
        if self._utility.has_collection(coll_name):
            self._collection = self._Collection(coll_name)
            self._collection.load()
            print(f"[Milvus] 集合已存在: {coll_name}")
        else:
            fields = [
                self._FieldSchema(name="id", dtype=self._DataType.VARCHAR, max_length=64, is_primary=True),
                self._FieldSchema(name="kb_id", dtype=self._DataType.INT64),
                self._FieldSchema(name="doc_id", dtype=self._DataType.INT64),
                self._FieldSchema(name="chunk_index", dtype=self._DataType.INT64),
                self._FieldSchema(name="text", dtype=self._DataType.VARCHAR, max_length=4096),
                self._FieldSchema(name="embedding", dtype=self._DataType.FLOAT_VECTOR, dim=self._dim),
            ]
            schema = self._CollectionSchema(fields, description="medical chunks")
            self._collection = self._Collection(coll_name, schema)

            # 创建索引
            index_params = {
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {"M": 16, "efConstruction": 200},
            }
            self._collection.create_index(field_name="embedding", index_params=index_params)
            self._collection.load()
            print(f"[Milvus] 集合创建成功: {coll_name}")

    def insert(self, record: VectorRecord):
        self.insert_batch([record])

    def insert_batch(self, records: list[VectorRecord]):
        if not self._connect() or not records:
            return
        data = [
            [r.id for r in records],
            [r.kb_id for r in records],
            [r.doc_id for r in records],
            [r.chunk_index for r in records],
            [r.text[:4000] for r in records],
            [r.embedding for r in records],
        ]
        self._collection.insert(data)
        self._collection.flush()

    def delete_by_doc(self, doc_id: int):
        if not self._connect():
            return
        expr = f"doc_id == {doc_id}"
        self._collection.delete(expr)

    def delete_by_kb(self, kb_id: int):
        if not self._connect():
            return
        expr = f"kb_id == {kb_id}"
        self._collection.delete(expr)

    def search(
        self,
        query_vec: np.ndarray,
        kb_ids: list[int],
        top_k: int = config.TOP_K,
        min_similarity: float = config.MIN_SIMILARITY,
    ) -> list[dict]:
        if not self._connect():
            return []

        # 构造过滤表达式
        if kb_ids:
            ids_str = ",".join(str(int(i)) for i in kb_ids)
            expr = f"kb_id in [{ids_str}]"
        else:
            expr = ""

        search_params = {"metric_type": "COSINE", "params": {"ef": 64}}
        results = self._collection.search(
            data=[query_vec.tolist()],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["id", "kb_id", "doc_id", "chunk_index", "text"],
        )

        out = []
        for hit in results[0]:
            sim = float(hit.score)
            if sim < min_similarity:
                continue
            entity = hit.entity
            out.append({
                "id": entity.get("id"),
                "kb_id": entity.get("kb_id"),
                "doc_id": entity.get("doc_id"),
                "chunk_index": entity.get("chunk_index"),
                "text": entity.get("text"),
                "similarity": sim,
            })
        return out

    @property
    def count(self) -> int:
        if not self._connect():
            return 0
        return self._collection.num_entities

    def get_all_chunks(self) -> list[dict]:
        """
        导出全部 chunk（供 BM25 等稀疏检索器构建索引）。

        Milvus 侧按主键分页拉取全部实体；集合为空时返回 []。
        """
        if not self._connect():
            return []
        out: list[dict] = []
        try:
            # Milvus query 不支持无 expr 全量扫描，使用恒成立 expr + 分页
            page = 0
            page_size = 1000
            while True:
                rows = self._collection.query(
                    expr="",
                    output_fields=["id", "kb_id", "doc_id", "chunk_index", "text"],
                    offset=page * page_size,
                    limit=page_size,
                )
                if not rows:
                    break
                for r in rows:
                    out.append(
                        {
                            "id": r.get("id"),
                            "kb_id": r.get("kb_id"),
                            "doc_id": r.get("doc_id"),
                            "chunk_index": r.get("chunk_index"),
                            "text": r.get("text"),
                        }
                    )
                if len(rows) < page_size:
                    break
                page += 1
        except Exception as e:  # noqa: BLE001
            print(f"[Milvus] get_all_chunks 失败（返回已收集部分）: {e}")
        return out

    def clear(self) -> None:
        """清空全部向量（重建索引前调用）。

        Milvus 不支持空 expr 的 delete，先取出全部主键再按主键集合删除。
        """
        if not self._connect():
            return
        try:
            ids: list = []
            page = 0
            page_size = 1000
            while True:
                rows = self._collection.query(
                    expr="",
                    output_fields=["id"],
                    offset=page * page_size,
                    limit=page_size,
                )
                if not rows:
                    break
                ids.extend(r["id"] for r in rows)
                if len(rows) < page_size:
                    break
                page += 1
            if not ids:
                return
            # 分块删除，避免 expr 过长
            for i in range(0, len(ids), 200):
                batch = ids[i : i + 200]
                id_list = ", ".join(f'"{v}"' for v in batch)
                self._collection.delete(expr=f"id in [{id_list}]")
            self._collection.flush()
        except Exception as e:  # noqa: BLE001
            print(f"[Milvus] clear 失败: {e}")


# ---- 全局单例 ----
_store: Optional[object] = None
_store_lock = threading.Lock()


def _milvus_ready_within(store, timeout: int = 30) -> bool:
    """在后台线程中连接并加载 Milvus 集合，超时则返回 False。

    避免 Milvus 不可用 / 加载缓慢时阻塞整个应用进程（原逻辑会在
    collection.load() 上无限等待，导致所有向量相关请求卡死）。
    """
    box: dict = {}

    def _run():
        try:
            box["ok"] = store._connect()
        except Exception as e:  # noqa: BLE001
            box["err"] = e
            box["ok"] = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        # 超时仍在加载：判定为不可用，交由 NumpyStore 兜底
        return False
    return bool(box.get("ok", False))


def get_vectorstore():
    """获取向量存储实例（Milvus 优先，NumpyStore 兜底）。"""
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store

        if config.MILVUS_ENABLE:
            try:
                store = MilvusStore()
                if _milvus_ready_within(store, timeout=30):
                    _store = store
                    print("[VectorStore] 使用 Milvus")
                    return _store
                else:
                    print("[VectorStore] Milvus 连接/加载超时，降级到 NumpyStore")
            except Exception as e:  # noqa: BLE001
                print(f"[VectorStore] Milvus 不可用，降级到 NumpyStore: {e}")

        _store = NumpyStore()
        print("[VectorStore] 使用 NumpyStore（纯 Python 兜底）")
        return _store
