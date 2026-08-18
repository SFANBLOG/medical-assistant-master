"""向量存储层：Milvus（首选）+ NumpyStore（纯 Python 兜底）。

统一接口（各 store 行为一致）：
- upsert(kb_id, ids, embeddings, documents, metadatas)  入库（幂等，同 id 覆盖）
- query(kb_id, embedding, top_k, filters=None)           检索，返回 cosine 距离
- delete_doc(kb_id, doc_id)                              删除某文档全部切片
- delete_collection(kb_id)                               删除某知识库全部切片

约定：
- 命中列表中的 distance 为 **cosine 距离**（取值范围 [0, 2]），
  相似度 = 1 - distance（对归一化向量即 cosine 相似度，完全一致时 ≈ 1.0）。
  供 services.retriever 直接使用，避免 1/(1+d) 这类压分映射。
- filters 为可选标量等值过滤，如 {"visibility": "public"}，同时支持 Milvus 与 numpy 实现。
"""
import json
import logging
import os
import threading

import numpy as np

logger = logging.getLogger(__name__)

# 相似度低于该值视为无关（用于过滤检索噪音；返回 top_k 不受此影响）…
# 说明：NumpyStore 会丢弃低于阈值的命中；Milvus 端用 search 的 radius 过滤。
DEFAULT_MIN_SIMILARITY = 0.30


class VectorStoreError(RuntimeError):
    """向量存储层错误（维度不匹配 / 后端不可用等）。"""


class MilvusUnavailable(VectorStoreError):
    """Milvus 服务不可用。调用方应降级到 NumpyStore。"""


class NumpyStore:
    """轻量纯 Python 向量存储（numpy 暴力 cosine 检索 + JSON/npy 磁盘持久化）。

    作为 Milvus 不可用时的兜底；与 MilvusStore 返回一致的 cosine 距离。
    """

    def __init__(self, persist_dir: str, dim: int = 1024, min_similarity: float = DEFAULT_MIN_SIMILARITY):
        self.persist_dir = persist_dir
        self.dim = dim
        self.min_similarity = min_similarity
        self._lock = threading.Lock()
        os.makedirs(persist_dir, exist_ok=True)
        logger.info(f"NumpyStore init, persist_dir={persist_dir}, dim={self.dim}")

    def _paths(self, kb_id: int) -> tuple[str, str]:
        base = os.path.join(self.persist_dir, f"kb_{kb_id}")
        return base + ".npy", base + ".json"

    def _load(self, kb_id: int):
        arr_path, meta_path = self._paths(kb_id)
        if not (os.path.exists(arr_path) and os.path.exists(meta_path)):
            return np.zeros((0, self.dim), dtype=np.float32), []
        arr = np.load(arr_path).astype(np.float32)
        # 校验磁盘向量维度，不匹配直接报错，避免静默计算错误
        if arr.ndim == 2 and arr.shape[1] != self.dim:
            raise VectorStoreError(
                f"NumpyStore维度不匹配！配置dim={self.dim},磁盘npy向量dim={arr.shape[1]}。"
                "请删除向量目录后重新入库（EMBED_DIM 已变更）。"
            )
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        return arr, meta

    def _save(self, kb_id: int, arr: np.ndarray, meta: list[dict]) -> None:
        arr_path, meta_path = self._paths(kb_id)
        np.save(arr_path, arr)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

    @staticmethod
    def _normalize(vecs: np.ndarray) -> np.ndarray:
        """L2 归一化（cosine 检索统一用单位向量，零向量保留原样）。"""
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

    def upsert(self, kb_id: int, ids, embeddings, documents, metadatas) -> None:
        with self._lock:
            arr, meta = self._load(kb_id)
            new_arr = np.asarray(embeddings, dtype=np.float32)
            if new_arr.ndim != 2 or new_arr.shape[1] != self.dim:
                raise VectorStoreError(
                    f"upsert向量维度错误！store dim={self.dim},输入embedding shape={new_arr.shape}"
                )
            new_arr = self._normalize(new_arr)
            for i, cid in enumerate(ids):
                meta.append(
                    {"id": cid, "document": documents[i], "metadata": metadatas[i]}
                )
            arr = np.concatenate([arr, new_arr], axis=0) if len(arr) else new_arr
            self._save(kb_id, arr, meta)
            logger.debug(f"kb_id={kb_id} upsert done, total vector count={len(arr)}")

    def query(self, kb_id: int, embedding: list[float], top_k: int = 5,
              filters: dict | None = None) -> list[dict]:
        """检索：返回按 cosine 距离升序的命中（distance=1-cos，越小越相似）。"""
        filters = filters or {}
        with self._lock:
            arr, meta = self._load(kb_id)
        if len(arr) == 0:
            logger.warning(f"kb_id={kb_id} vector store empty")
            return []

        vec = np.asarray(embedding, dtype=np.float32)
        if vec.ndim != 1 or vec.shape[0] != self.dim:
            raise VectorStoreError(
                f"query向量维度错误！store dim={self.dim}, query vec dim={vec.shape[0] if vec.ndim else '?'}"
            )
        norm = np.linalg.norm(vec)
        vec = vec / norm if norm > 0 else vec

        cos = (self._normalize(arr) @ vec).astype(np.float32)  # cosine 相似度
        cos = np.clip(cos, -1.0, 1.0)
        dists = (1.0 - cos).astype(np.float32)  # cosine 距离

        order = np.argsort(dists)
        hits = []
        for idx in order:
            dist = float(dists[idx])
            # 距离升序：一旦低于阈值，后续全部更低，直接结束
            if (1.0 - dist) < self.min_similarity:
                break
            if len(hits) >= top_k:
                break
            entry = meta[int(idx)]
            md = entry.get("metadata") or {}
            # 标量过滤（如 visibility）
            if filters and any(md.get(k) != v for k, v in filters.items()):
                continue
            hits.append(
                {
                    "id": entry["id"],
                    "text": entry["document"],
                    "metadata": md,
                    "distance": dist,
                }
            )
        logger.debug(f"query kb_id={kb_id}, top_k={top_k}, valid hit count={len(hits)}")
        return hits

    def delete_doc(self, kb_id: int, doc_id: int) -> None:
        with self._lock:
            arr, meta = self._load(kb_id)
            keep = [i for i, e in enumerate(meta) if e["metadata"].get("doc_id") != doc_id]
            if len(keep) == len(meta):
                return
            new_arr = arr[keep] if keep else np.zeros((0, self.dim), dtype=np.float32)
            new_meta = [meta[i] for i in keep]
            self._save(kb_id, new_arr, new_meta)

    def delete_collection(self, kb_id: int) -> None:
        with self._lock:
            arr_path, meta_path = self._paths(kb_id)
            for p in (arr_path, meta_path):
                try:
                    os.remove(p)
                except OSError:
                    pass
            logger.info(f"delete_collection kb_id={kb_id} finished")


class MilvusStore:
    """Milvus 向量库实现（自定义集合设计）。

    集合设计（单集合 + kb_id 分区键，便于按知识库高效隔离与过滤）：
      id          VARCHAR(64)  主键           = "<doc_id>:<chunk_index>"
      kb_id       INT64        分区键 partition_key
      doc_id      INT64
      chunk_index INT64
      filename    VARCHAR(512)
      visibility  VARCHAR(16)
      text        VARCHAR(65535)  切片原文
      vector      FLOAT_VECTOR(dim)  归一化向量
    相似度度量：COSINE（Milvus 返回 distance = 1 - cosine，与 NumpyStore 一致）。
    """

    COLLECTION_NAME = "medical_chunks"

    def __init__(self, host: str = "127.0.0.1", port: int = 19530, dim: int = 1024,
                 db_name: str = "default", collection: str | None = None,
                 min_similarity: float = DEFAULT_MIN_SIMILARITY):
        self.host = host
        self.port = int(port)
        self.dim = dim
        self.db_name = db_name
        self.collection_name = collection or self.COLLECTION_NAME
        self.min_similarity = min_similarity
        self._lock = threading.Lock()
        self._col = None
        self._connected = False
        self._connect()

    # ---- 连接与集合管理 ----
    def _connect(self):
        if self._connected:
            return
        try:
            from pymilvus import Collection, connections  # 延迟导入，保证 pymilvus 可选
        except ImportError as e:  # pragma: no cover
            raise MilvusUnavailable(f"未安装 pymilvus: {e}") from e
        try:
            connections.connect(
                alias="default", host=self.host, port=self.port, db_name=self.db_name
            )
            self._connected = True
        except Exception as e:  # noqa: BLE001 Milvus 未启动 / 网络不可达
            raise MilvusUnavailable(f"无法连接 Milvus({self.host}:{self.port}): {e}") from e

    def _ensure_collection(self):
        """创建（或复用）集合；校验维度一致性。"""
        if self._col is not None:
            return self._col
        with self._lock:
            from pymilvus import (Collection, CollectionSchema, DataType,
                                  FieldSchema, utility)

            if utility.has_collection(self.collection_name, using="default"):
                col = Collection(self.collection_name, using="default")
                vector_field = next(
                    (f for f in col.schema.fields if f.dtype == DataType.FLOAT_VECTOR), None
                )
                if vector_field is None or vector_field.params.get("dim") != self.dim:
                    raise VectorStoreError(
                        f"Milvus集合 {self.collection_name} 向量维度不匹配！"
                        f"集合dim={vector_field.params.get('dim') if vector_field else '?'}，"
                        f"配置EMBED_DIM={self.dim}。请先删除集合或调小 EMBED_DIM 后重新入库。"
                    )
                try:
                    col.load()
                except Exception:  # noqa: BLE001 空集合可能未加载
                    pass
                self._col = col
                return col

            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
                FieldSchema(name="kb_id", dtype=DataType.INT64, is_partition_key=True),
                FieldSchema(name="doc_id", dtype=DataType.INT64),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="visibility", dtype=DataType.VARCHAR, max_length=16),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
            ]
            schema = CollectionSchema(
                fields, description="医智助手知识库向量片段（kb_id 分区键 + cosine 度量）"
            )
            col = Collection(self.collection_name, schema=schema, using="default",
                             consistency_level="Session")
            col.create_index(
                "vector",
                {"index_type": "HNSW", "metric_type": "COSINE",
                 "params": {"M": 16, "efConstruction": 200}},
            )
            col.load()
            self._col = col
            logger.info(f"MilvusStore 创建集合 {self.collection_name} (dim={self.dim})")
            return col

    def _expr(self, kb_id: int, filters: dict | None) -> str:
        expr = f"kb_id == {int(kb_id)}"
        if filters:
            for k, v in filters.items():
                expr += f" and {k} == '{v}'"
        return expr

    # ---- 统一接口 ----
    def upsert(self, kb_id: int, ids, embeddings, documents, metadatas) -> None:
        col = self._ensure_collection()
        rows = []
        for i, cid in enumerate(ids):
            vec = list(embeddings[i])
            if len(vec) != self.dim:
                raise VectorStoreError(
                    f"Milvus upsert向量维度错误！collection dim={self.dim}, "
                    f"输入embedding dim={len(vec)}"
                )
            md = metadatas[i]
            rows.append(
                {
                    "id": str(cid),
                    "kb_id": int(kb_id),
                    "doc_id": int(md.get("doc_id", 0)),
                    "chunk_index": int(md.get("chunk_index", 0)),
                    "filename": str(md.get("filename", ""))[:512],
                    "visibility": str(md.get("visibility", "public"))[:16],
                    "text": documents[i][:65535],
                    "vector": vec,
                }
            )
        with self._lock:
            col.upsert(rows)
            col.flush()
        logger.debug(f"Milvus upsert kb_id={kb_id}, rows={len(rows)}")

    def query(self, kb_id: int, embedding: list[float], top_k: int = 5,
              filters: dict | None = None) -> list[dict]:
        col = self._ensure_collection()
        vec = list(embedding)
        if len(vec) != self.dim:
            raise VectorStoreError(
                f"Milvus query向量维度错误！collection dim={self.dim}, query vec dim={len(vec)}"
            )
        # 过采样以保证标量过滤（如 visibility）与相似度阈值过滤后仍有足够结果
        search_limit = max(top_k * 4, top_k + 8)
        res = col.search(
            data=[vec],
            anns_field="vector",
            param={"metric_type": "COSINE", "params": {"ef": 128}},
            limit=search_limit,
            expr=self._expr(kb_id, filters),
            output_fields=["id", "doc_id", "chunk_index", "filename", "visibility", "text"],
        )
        hits = []
        for hit in res[0]:
            if len(hits) >= top_k:
                break
            distance = float(hit.distance)
            # 相似度过低视为无关（与 NumpyStore 行为一致）
            if (1.0 - distance) < self.min_similarity:
                continue
            entity = hit.entity
            hits.append(
                {
                    "id": hit.id,
                    "text": entity.get("text", ""),
                    "metadata": {
                        "doc_id": entity.get("doc_id"),
                        "kb_id": kb_id,
                        "chunk_index": entity.get("chunk_index"),
                        "filename": entity.get("filename", ""),
                        "visibility": entity.get("visibility", "public"),
                    },
                    "distance": distance,
                }
            )
        return hits

    def delete_doc(self, kb_id: int, doc_id: int) -> None:
        col = self._ensure_collection()
        with self._lock:
            col.delete(expr=f"kb_id == {int(kb_id)} and doc_id == {int(doc_id)}")
            col.flush()

    def delete_collection(self, kb_id: int) -> None:
        col = self._ensure_collection()
        with self._lock:
            col.delete(expr=f"kb_id == {int(kb_id)}")
            col.flush()
