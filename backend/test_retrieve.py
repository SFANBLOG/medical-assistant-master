# -*- coding: utf-8 -*-
"""
临时测试脚本：验证混合检索流水线
    BM25 top30 + 稠密 top30 → 合并去重 → Cross-Encoder 重排 → top-N
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config  # noqa: E402
from backend.rag.retriever import retrieve, _ensure_bm25, rebuild_bm25  # noqa: E402
from backend.rag.vectorstore import get_vectorstore  # noqa: E402
from backend.rag.embedder import get_embedder  # noqa: E402
from backend.rag.bm25 import BM25Index  # noqa: E402


def show_pipeline(query: str, role: str, user_id: int, kb_id):
    print("\n" + "=" * 74)
    print(f"QUERY: {query}   (role={role}, kb_id={kb_id})")
    print("=" * 74)

    vs = get_vectorstore()
    emb = get_embedder()
    from backend.rag.retriever import _get_visible_kb_ids
    kb_ids = _get_visible_kb_ids(role, user_id, kb_id)
    print(f"[阶段0] 可见知识库 {len(kb_ids)} 个")

    # 阶段1a 稠密
    qv = emb.embed(query)
    dense = vs.search(qv, kb_ids, top_k=config.DENSE_TOP_K,
                      min_similarity=config.DENSE_MIN_SIMILARITY)
    print(f"[阶段1] 稠密召回 {len(dense)} 条 | BM25 召回")

    # 阶段1b BM25
    rebuild_bm25()
    bm25 = _ensure_bm25()
    sparse = bm25.search(query, kb_ids, top_k=config.BM25_TOP_K) if bm25 else []
    print(f"[阶段1] BM25 召回 {len(sparse)} 条")

    # 阶段2 合并去重
    merged = {}
    for h in dense:
        merged[(h["doc_id"], h["chunk_index"])] = 1
    for h in sparse:
        merged[(h["doc_id"], h["chunk_index"])] = 1
    print(f"[阶段2] 合并去重后候选 {len(merged)} 条")

    # 阶段3 重排（retrieve 内部完成）
    hits = retrieve(query, role, user_id, kb_id=kb_id)
    print(f"[阶段3] Cross-Encoder 重排后保留 {len(hits)} 条 "
          f"(RERANK_TOP_K={config.RERANK_TOP_K}, MIN_SCORE={config.RERANK_MIN_SCORE})")
    print("-" * 74)
    for i, h in enumerate(hits, 1):
        print(f"  [{i}] {h['filename']:.<28} 相似度={h['similarity']:.3f}  kb={h.get('kb_name')}")
        print(f"       {h['text'][:60].replace(chr(10), ' ')}")
    return hits


def main():
    print(f"BM25_TOP_K={config.BM25_TOP_K}, DENSE_TOP_K={config.DENSE_TOP_K}, "
          f"RERANK_TOP_K={config.RERANK_TOP_K}, RERANK_MIN_SCORE={config.RERANK_MIN_SCORE}")

    # 关键回归用例：之前问糖尿病却引到《肥胖症.md》且相似度仅 30.2%
    show_pipeline("糖尿病患者能吃水果吗？", "patient", 1, 0)
    show_pipeline("高血压患者日常饮食要注意什么？", "patient", 1, 0)
    show_pipeline("感冒发烧应该注意什么？", "public", 1, 0)

    # 无关问题：应当被重排过滤掉（或只剩极少低分）
    show_pipeline("如何用 Python 实现快速排序？", "patient", 1, 0)


if __name__ == "__main__":
    main()
