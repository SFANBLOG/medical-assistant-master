"""
向量存储：Milvus 主方案 + NumpyStore 纯 Python 兜底。

- Milvus 集合 `medical_chunks`：字段 (id, kb_id, doc_id, chunk_index, text, embedding)
  cosine 度量 + HNSW 索引
- NumpyStore：内存 dict + numpy 数组，cosine 相似度，功能等价；
  数据自动持久化到 backend/data/numpy_store.pkl（进程重启后仍可检索）

注意：MilvusStore 已迁移到 PyMilvus 3.x 推荐的 `MilvusClient` API，
避免 ORM 风格 API（connections / Collection / utility）在 PyMilvus 3.1 中被移除。
"""
import os
import pickle
import threading
import time
from dataclasses import dataclass, field
from pickle import Unpickler
from typing import Optional

import numpy as np

from backend import config
from backend.rag.embedder import get_embedder

# 兼容旧版打包路径：重构前向量记录以 `rag.*` 等顶层包名序列化，
# 重构后统一为 `backend.*`，反序列化时做一次性路径映射。
_OLD_TOP_PKGS = ("rag", "utils", "services", "routes", "models", "seed", "config")


class _CompatUnpickler(Unpickler):
    """兼容反序列化器：将旧模块路径 `rag.*` 等映射到 `backend.*`。"""

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
        self._embedder = get_embedder()
        self._dim = self._embedder.dim
        # 持久化路径：进程重启后从磁盘恢复向量
        self._persist_path = config.DATA_DIR / "numpy_store.pkl"
        self._load_from_disk()

    def _load_from_disk(self):
        """启动时从磁盘加载向量数据。

        使用兼容反序列化器，可正确加载重构前（模块路径为 `rag.*` 等）保存的 pickle。
        """
        try:
            if self._persist_path.exists() and self._persist_path.stat().st_size > 0:
                with open(self._persist_path, "rb") as f:
                    self._records = _CompatUnpickler(f).load()
                if not isinstance(self._records, dict):
                    self._records = {}
                self._dirty = True
                print(f"[NumpyStore] 从磁盘加载 {len(self._records)} 条向量记录")
        except Exception as e:  # noqa: BLE001
            print(f"[NumpyStore] 加载持久化数据失败（忽略）: {e}")
            self._records = {}

    def _save_to_disk(self):
        """将向量数据持久化到磁盘。

        写入进程/线程独立的临时文件后做原子替换；对 Windows 文件锁错误
        （WinError 32：目标 pkl 被另一进程占用，常见于 Flask watchdog 热重载
        窗口）做有限次退避重试，避免增量向量因 replace 失败而丢失。

        注意：临时文件名自带 pid+tid，且用普通 open 写入（不依赖
        tempfile.mkstemp，避免其返回的底层 fd 泄漏导致源文件被占用、
        在 Windows 上 os.replace 直接报 WinError 32 的坑）。
        """
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            # 独立临时文件名（带 pid+tid），避免多进程/多线程共用同一 tmp 互相覆盖
            tmp_name = self._persist_path.with_name(
                f"{self._persist_path.stem}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            try:
                with open(tmp_name, "wb") as f:
                    pickle.dump(self._records, f, protocol=pickle.HIGHEST_PROTOCOL)
                    f.flush()
                    os.fsync(f.fileno())
            except BaseException:
                # 写入失败清理临时文件，避免残留
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
                raise
            # 原子替换，遇文件锁重试（Windows 上目标被占用会抛 PermissionError/WinError 32）
            last_err: Optional[Exception] = None
            for attempt in range(15):
                try:
                    os.replace(tmp_name, self._persist_path)
                    return
                except PermissionError as e:  # noqa: BLE001  Windows WinError 32
                    last_err = e
                    if attempt == 0:
                        print("[NumpyStore] 持久化被文件锁占用，重试中…(WinError 32)")
                    time.sleep(0.1)
                except OSError as e:  # noqa: BLE001  兜底捕获其它替换错误
                    last_err = e
                    if attempt == 0:
                        print(f"[NumpyStore] 持久化临时失败，重试中…({e})")
                    time.sleep(0.1)
            # 重试耗尽：尽量保留临时文件供排查，并记录错误
            print(f"[NumpyStore] 持久化失败（重试耗尽）: {last_err}")
        except Exception as e:  # noqa: BLE001
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
    """Milvus 向量存储（基于 PyMilvus 3.x 的 MilvusClient）。"""

    def __init__(self):
        # 延迟导入：Milvus 未启用时避免引入 pymilvus
        from pymilvus import FieldSchema, CollectionSchema, DataType
        self._FieldSchema = FieldSchema
        self._CollectionSchema = CollectionSchema
        self._DataType = DataType

        self._client = None          # MilvusClient 实例
        self._connected = False
        self._last_error = None      # 最近一次连接失败的异常，供调用方区分原因
        self._embedder = get_embedder()
        self._dim = self._embedder.dim

    def _connect(self) -> bool:
        """连接 Milvus，成功返回 True。

        使用 MilvusClient（PyMilvus 3.x 推荐 API），构造时即建立连接。
        - 连接成功：加载/创建集合后返回 True
        - 连接被拒绝 / 服务未启动：立即捕获，记录 _last_error，返回 False
        - 连接超时：抛出异常，由 _milvus_ready_within 按超时处理

        注意区分「服务未启动（连接被拒绝）」与「连接超时」两种失败，
        避免把本地没起 Milvus 的常态误报成「超时」。
        """
        if self._connected and self._client is not None:
            return True
        try:
            from pymilvus import MilvusClient
            uri = f"http://{config.MILVUS_HOST}:{config.MILVUS_PORT}"
            # 用可配置的短超时：本地未启动 Milvus 时快速失败，不阻塞启动流程
            self._client = MilvusClient(uri=uri, timeout=config.MILVUS_CONNECT_TIMEOUT)
            self._connected = True
            self._last_error = None
            print(f"[Milvus] 连接成功: {config.MILVUS_HOST}:{config.MILVUS_PORT}")
            self._ensure_collection()
            return True
        except Exception as e:  # noqa: BLE001
            self._last_error = e
            self._connected = False
            self._client = None
            # 区分「服务未启动 / 地址不可达」与「真正超时」，给出更准确的提示
            msg = str(e).lower()
            if "unavailable" in msg or "refused" in msg or "code=2" in msg:
                print(
                    f"[Milvus] 连接失败（服务未启动或地址不可达）: "
                    f"{config.MILVUS_HOST}:{config.MILVUS_PORT}"
                )
            else:
                print(f"[Milvus] 连接失败: {e}")
            return False

    def _ensure_collection(self):
        """确保集合存在，不存在则创建并建立 HNSW 索引。"""
        if not self._connected or self._client is None:
            return

        coll_name = config.MILVUS_COLLECTION
        if self._client.has_collection(coll_name):
            # 集合已存在：加载到内存即可
            self._client.load_collection(coll_name)
            print(f"[Milvus] 集合已存在: {coll_name}")
        else:
            # 构建 Schema
            fields = [
                self._FieldSchema(name="id", dtype=self._DataType.VARCHAR, max_length=64, is_primary=True),
                self._FieldSchema(name="kb_id", dtype=self._DataType.INT64),
                self._FieldSchema(name="doc_id", dtype=self._DataType.INT64),
                self._FieldSchema(name="chunk_index", dtype=self._DataType.INT64),
                self._FieldSchema(name="text", dtype=self._DataType.VARCHAR, max_length=4096),
                self._FieldSchema(name="embedding", dtype=self._DataType.FLOAT_VECTOR, dim=self._dim),
            ]
            schema = self._CollectionSchema(fields, description="medical chunks")

            # 构建索引参数：HNSW + COSINE
            index_params = self._client.prepare_index_params()
            index_params.add_index(
                field_name="embedding",
                index_type="HNSW",
                metric_type="COSINE",
                params={"M": 16, "efConstruction": 200},
            )

            self._client.create_collection(
                collection_name=coll_name,
                schema=schema,
                index_params=index_params,
            )
            self._client.load_collection(coll_name)
            print(f"[Milvus] 集合创建成功: {coll_name}")

    def _records_to_dicts(self, records: list[VectorRecord]) -> list[dict]:
        """将 VectorRecord 列表转换为 MilvusClient 要求的 dict 列表。"""
        return [
            {
                "id": r.id,
                "kb_id": r.kb_id,
                "doc_id": r.doc_id,
                "chunk_index": r.chunk_index,
                "text": r.text[:4000],
                "embedding": r.embedding,
            }
            for r in records
        ]

    def insert(self, record: VectorRecord):
        self.insert_batch([record])

    def insert_batch(self, records: list[VectorRecord]):
        if not self._connect() or not records:
            return
        data = self._records_to_dicts(records)
        self._client.insert(collection_name=config.MILVUS_COLLECTION, data=data)
        self._client.flush(collection_name=config.MILVUS_COLLECTION)

    def delete_by_doc(self, doc_id: int):
        if not self._connect():
            return
        expr = f"doc_id == {doc_id}"
        self._client.delete(collection_name=config.MILVUS_COLLECTION, filter=expr)

    def delete_by_kb(self, kb_id: int):
        if not self._connect():
            return
        expr = f"kb_id == {kb_id}"
        self._client.delete(collection_name=config.MILVUS_COLLECTION, filter=expr)

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
        expr = f"kb_id in [{','.join(str(int(i)) for i in kb_ids)}]" if kb_ids else ""

        search_params = {"metric_type": "COSINE", "params": {"ef": 64}}
        # 兼容 query_vec 为 numpy 数组或普通 list
        query_data = [np.asarray(query_vec, dtype=np.float32).tolist()]
        results = self._client.search(
            collection_name=config.MILVUS_COLLECTION,
            data=query_data,
            anns_field="embedding",
            search_params=search_params,
            limit=top_k,
            filter=expr,
            output_fields=["id", "kb_id", "doc_id", "chunk_index", "text"],
        )

        out = []
        # MilvusClient.search 返回 List[List[dict]]，外层按输入向量分组
        for group in results:
            for hit in group:
                sim = float(hit.get("distance", 0.0))
                if sim < min_similarity:
                    continue
                out.append({
                    "id": hit.get("id"),
                    "kb_id": hit.get("kb_id"),
                    "doc_id": hit.get("doc_id"),
                    "chunk_index": hit.get("chunk_index"),
                    "text": hit.get("text"),
                    "similarity": sim,
                })
        return out

    @property
    def count(self) -> int:
        if not self._connect():
            return 0
        # MilvusClient 2.5+ 已移除 ORM 的 num_entities，改用 get_collection_stats
        stats = self._client.get_collection_stats(collection_name=config.MILVUS_COLLECTION)
        # 返回结构形如 {"row_count": N, "partitions": [...]}
        return int(stats.get("row_count", 0))

    def get_all_chunks(self) -> list[dict]:
        """
        导出全部 chunk（供 BM25 等稀疏检索器构建索引）。

        Milvus 侧按主键分页拉取全部实体；集合为空时返回 []。
        """
        if not self._connect():
            return []
        out: list[dict] = []
        try:
            # Milvus query 通常不允许无 filter 的全量扫描，使用空 filter + 分页兜底
            page = 0
            page_size = 1000
            while True:
                rows = self._client.query(
                    collection_name=config.MILVUS_COLLECTION,
                    filter="",
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

        Milvus 不支持空 filter 的 delete，先取出全部主键再按主键集合删除。
        """
        if not self._connect():
            return
        try:
            ids: list = []
            page = 0
            page_size = 1000
            while True:
                rows = self._client.query(
                    collection_name=config.MILVUS_COLLECTION,
                    filter="",
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
            # 分块删除，避免 filter 过长
            for i in range(0, len(ids), 200):
                batch = ids[i : i + 200]
                self._client.delete(collection_name=config.MILVUS_COLLECTION, ids=batch)
            self._client.flush(collection_name=config.MILVUS_COLLECTION)
        except Exception as e:  # noqa: BLE001
            print(f"[Milvus] clear 失败: {e}")


# ---- 全局单例 ----
_store: Optional[object] = None
_store_lock = threading.Lock()


def _milvus_ready_within(store, timeout: int = 30) -> tuple[bool, bool]:
    """在后台线程中连接并加载 Milvus 集合，返回 (是否就绪, 是否超时)。

    返回 (False, True)  表示线程在 timeout 内仍未结束 —— 真正「超时」
    （服务可达但加载/响应过慢），交由 NumpyStore 兜底；
    返回 (False, False) 表示连接被快速拒绝（服务未启动），同样兜底。

    这样调用方可以区分「服务未启动」与「连接超时」两种失败，避免误报。
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
        return False, True
    return bool(box.get("ok", False)), False


def get_vectorstore():
    """获取向量存储实例（Milvus 优先，NumpyStore 兜底）。"""
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store

        # 显式关闭时直接使用 NumpyStore，不尝试连接 Milvus
        if not config.MILVUS_ENABLE:
            _store = NumpyStore()
            print("[VectorStore] MILVUS_ENABLE=0，使用 NumpyStore（纯 Python 兜底）")
            return _store

        try:
            store = MilvusStore()
            # 超时上限 = 连接超时 + 2s 缓冲；超过即视为加载过慢而降级
            ok, timed_out = _milvus_ready_within(
                store, timeout=config.MILVUS_CONNECT_TIMEOUT + 2
            )
            if ok:
                _store = store
                print("[VectorStore] 使用 Milvus")
                return _store
            if timed_out:
                # 真正超时（服务可达但响应过慢）：本地开发罕见，提示调大超时
                print(
                    f"[VectorStore] Milvus 连接超时（>{config.MILVUS_CONNECT_TIMEOUT}s），"
                    f"降级到 NumpyStore"
                )
            else:
                # 连接被快速拒绝（本地未启动 Milvus 是常态）：给出可执行提示
                print(
                    "[VectorStore] Milvus 不可用（本地未启动或地址错误），"
                    "已降级到 NumpyStore"
                )
        except Exception as e:  # noqa: BLE001
            print(f"[VectorStore] Milvus 初始化异常，降级到 NumpyStore: {e}")

        _store = NumpyStore()
        print("[VectorStore] 使用 NumpyStore（纯 Python 兜底）")
        return _store
