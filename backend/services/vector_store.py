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

    def get_chunks(self, kb_id: int, doc_ids, filters: dict | None = None) -> list[dict]:
        """按 doc_id 列表取回指定文档的全部切片（不计算相似度）。"""
        if not doc_ids:
            return []
        with self._lock:
            arr, meta = self._load(kb_id)
        idset = set(doc_ids)
        out = []
        for e in meta:
            md = e.get("metadata") or {}
            if md.get("doc_id") not in idset:
                continue
            if filters and any(md.get(k) != v for k, v in filters.items()):
                continue
            out.append(
                {
                    "id": e["id"],
                    "doc_id": md.get("doc_id"),
                    "chunk_index": md.get("chunk_index"),
                    "filename": md.get("filename", ""),
                    "text": e["document"],
                }
            )
        return out

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
    """Milvus 向量库实现（MilvusClient新版接口，无ORM弃用警告）。

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
        self._client = None
        self._connect()

    def _connect(self):
        if self._client is not None:
            return
        try:
            from pymilvus import MilvusClient
        except ImportError as e:
            raise MilvusUnavailable(f"未安装 pymilvus: {e}") from e
        try:
            self._client = MilvusClient(uri=f"http://{self.host}:{self.port}", db_name=self.db_name)
        except Exception as e:
            raise MilvusUnavailable(f"无法连接 Milvus({self.host}:{self.port}): {e}") from e

    def _ensure_collection(self):
        from pymilvus import DataType

        if self._client.has_collection(collection_name=self.collection_name):
            coll_info = self._client.describe_collection(collection_name=self.collection_name)
            vec_field = next(
                (f for f in coll_info["fields"] if f["type"] == DataType.FLOAT_VECTOR), None
            )
            if vec_field is None or vec_field["params"].get("dim") != self.dim:
                raise VectorStoreError(
                    f"Milvus集合 {self.collection_name} 向量维度不匹配！"
                    f"集合dim={vec_field['params']['dim'] if vec_field else '?'}，"
                    f"配置EMBED_DIM={self.dim}。请先删除集合或调小 EMBED_DIM 后重新入库。"
                )
            return

        schema = self._client.create_schema(
            auto_id=False,
            enable_dynamic_field=False
        )
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field(field_name="kb_id", datatype=DataType.INT64, is_partition_key=True)
        schema.add_field(field_name="doc_id", datatype=DataType.INT64)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
        schema.add_field(field_name="filename", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="visibility", datatype=DataType.VARCHAR, max_length=16)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.dim)

        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 200}
        )

        self._client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
            consistency_level="Session"
        )
        logger.info(f"MilvusStore 创建集合 {self.collection_name} (dim={self.dim})")

    def _expr(self, kb_id: int, filters: dict | None) -> str:
        expr = f"kb_id == {int(kb_id)}"
        if filters:
            for k, v in filters.items():
                expr += f" and {k} == '{v}'"
        return expr

    def upsert(self, kb_id: int, ids, embeddings, documents, metadatas) -> None:
        self._ensure_collection()
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
            self._client.upsert(collection_name=self.collection_name, data=rows)
            self._client.flush(collection_name=self.collection_name)
        logger.debug(f"Milvus upsert kb_id={kb_id}, rows={len(rows)}")

    def query(self, kb_id: int, embedding: list[float], top_k: int = 5,
              filters: dict | None = None) -> list[dict]:
        self._ensure_collection()
        vec = list(embedding)
        if len(vec) != self.dim:
            raise VectorStoreError(
                f"Milvus query向量维度错误！collection dim={self.dim}, query vec dim={len(vec)}"
            )
        search_limit = max(top_k * 4, top_k + 8)
        res = self._client.search(
            collection_name=self.collection_name,
            data=[vec],
            anns_field="vector",
            filter=self._expr(kb_id, filters),
            search_params={"metric_type": "COSINE", "params": {"ef": 128}},
            limit=search_limit,
            output_fields=["id", "doc_id", "chunk_index", "filename", "visibility", "text"],
        )
        hits = []
        for hit in res[0]:
            if len(hits) >= top_k:
                break
            distance = float(hit["distance"])
            if (1.0 - distance) < self.min_similarity:
                continue
            entity = hit["entity"]
            hits.append(
                {
                    "id": hit["id"],
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
        self._ensure_collection()
        with self._lock:
            self._client.delete(
                collection_name=self.collection_name,
                filter_expr=f"kb_id == {int(kb_id)} and doc_id == {int(doc_id)}"
            )
            self._client.flush(collection_name=self.collection_name)

    def get_chunks(self, kb_id: int, doc_ids, filters: dict | None = None) -> list[dict]:
        """按 doc_id 列表取回指定文档的全部切片（不计算相似度）。"""
        if not doc_ids:
            return []
        self._ensure_collection()
        doc_list = ",".join(str(int(d)) for d in doc_ids)
        expr = f"doc_id in [{doc_list}]"
        if filters:
            for k, v in filters.items():
                expr += f" and {k} == '{v}'"
        rows = self._client.query(
            collection_name=self.collection_name,
            filter=expr,
            output_fields=["id", "doc_id", "chunk_index", "filename", "text"],
        )
        return [
            {
                "id": r["id"],
                "doc_id": r["doc_id"],
                "chunk_index": r["chunk_index"],
                "filename": r.get("filename", ""),
                "text": r.get("text", ""),
            }
            for r in rows
        ]

    def delete_collection(self, kb_id: int) -> None:
        self._ensure_collection()
        with self._lock:
            self._client.delete(
                collection_name=self.collection_name,
                filter_expr=f"kb_id == {int(kb_id)}"
            )
            self._client.flush(collection_name=self.collection_name)
