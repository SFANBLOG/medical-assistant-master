# -*- coding: utf-8 -*-
"""临时诊断：对比 BM25 与稠密两路对同一 query 的排序差异。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.rag.retriever import _ensure_bm25, _get_visible_kb_ids  # noqa: E402
from backend.rag.vectorstore import get_vectorstore  # noqa: E402
from backend.rag.embedder import get_embedder  # noqa: E402
from backend import config  # noqa: E402

QUERY = "糖尿病患者能吃水果吗？"
role, user_id, kb_id = "patient", 1, 0

vs = get_vectorstore()
emb = get_embedder()
kb_ids = _get_visible_kb_ids(role, user_id, kb_id)

qv = emb.embed(QUERY)
dense = vs.search(qv, kb_ids, top_k=10, min_similarity=config.DENSE_MIN_SIMILARITY)
bm25 = _ensure_bm25()
sparse = bm25.search(QUERY, kb_ids, top_k=10)

from backend.utils.db import fetchall
docs = {r["id"]: r["filename"] for r in fetchall("SELECT id, filename FROM documents")}

print("=" * 70)
print("稠密向量 top10 (弱哈希嵌入)")
print("=" * 70)
for i, h in enumerate(dense, 1):
    print(f" {i:>2}. {docs.get(h['doc_id'], h['doc_id']):<26} cosine={h['similarity']:.4f}")

print()
print("=" * 70)
print("BM25 稀疏 top10")
print("=" * 70)
for i, h in enumerate(sparse, 1):
    print(f" {i:>2}. {docs.get(h['doc_id'], h['doc_id']):<26} bm25={h['bm25']:.4f}")
