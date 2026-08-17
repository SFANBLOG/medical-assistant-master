"""轻量纯 Python 向量存储（numpy 暴力检索 + JSON/npy 磁盘持久化）。

当 chromadb 在目标平台（如无 MSVC 编译工具的 Windows）无法安装时作为兜底，
接口与 extensions.ChromaStore 保持一致：upsert / query / delete_doc / delete_collection。
查询结果中的 distance 为 L2 距离，与 ChromaDB 的 hnsw:space=l2 语义一致。
"""
import json
import os
import threading

import numpy as np


class NumpyStore:
    def __init__(self, persist_dir: str, dim: int = 256):
        self.persist_dir = persist_dir
        self.dim = dim
        self._lock = threading.Lock()
        os.makedirs(persist_dir, exist_ok=True)

    def _paths(self, kb_id: int) -> tuple[str, str]:
        base = os.path.join(self.persist_dir, f"kb_{kb_id}")
        return base + ".npy", base + ".json"

    def _load(self, kb_id: int):
        arr_path, meta_path = self._paths(kb_id)
        if not (os.path.exists(arr_path) and os.path.exists(meta_path)):
            return np.zeros((0, self.dim), dtype=np.float32), []
        arr = np.load(arr_path).astype(np.float32)
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        return arr, meta

    def _save(self, kb_id: int, arr: np.ndarray, meta: list[dict]) -> None:
        arr_path, meta_path = self._paths(kb_id)
        np.save(arr_path, arr)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

    def upsert(self, kb_id: int, ids, embeddings, documents, metadatas) -> None:
        with self._lock:
            arr, meta = self._load(kb_id)
            new_arr = np.asarray(embeddings, dtype=np.float32)
            for i, cid in enumerate(ids):
                meta.append(
                    {"id": cid, "document": documents[i], "metadata": metadatas[i]}
                )
            arr = np.concatenate([arr, new_arr], axis=0) if len(arr) else new_arr
            self._save(kb_id, arr, meta)

    def query(self, kb_id: int, embedding: list[float], top_k: int = 5) -> list[dict]:
        with self._lock:
            arr, meta = self._load(kb_id)
        if len(arr) == 0:
            return []
        vec = np.asarray(embedding, dtype=np.float32)
        dists = np.linalg.norm(arr - vec, axis=1)
        top = np.argsort(dists)[:top_k]
        hits = []
        for idx in top:
            entry = meta[int(idx)]
            hits.append(
                {
                    "id": entry["id"],
                    "text": entry["document"],
                    "metadata": entry["metadata"],
                    "distance": float(dists[idx]),
                }
            )
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
