# -*- coding: utf-8 -*-
"""临时诊断：打印 query 各词条的 df 占比与对 top 文档的 BM25 贡献。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.rag.bm25 import _tokenize, BM25Index, MAX_DF_RATIO  # noqa: E402
from backend.rag.retriever import _ensure_bm25  # noqa: E402
from backend.utils.db import fetchall  # noqa: E402

QUERY = "糖尿病患者能吃水果吗？"
bm25 = _ensure_bm25()
docs = {r["id"]: r["filename"] for r in fetchall("SELECT id, filename FROM documents")}

toks = dict.fromkeys(_tokenize(QUERY))
N = bm25._N
print(f"N={N}, MAX_DF_RATIO={MAX_DF_RATIO}")
print("=" * 68)
print(f"{'token':<8} {'df':>5} {'df/N':>7}  {'idf':>6}  kept")
print("=" * 68)
kept = []
for t in toks:
    df = bm25._df.get(t, 0)
    ratio = df / N if N else 0
    idf = bm25._idf.get(t, 0.0)
    ok = df <= MAX_DF_RATIO * N
    if ok:
        kept.append(t)
    print(f"{t:<8} {df:>5} {ratio:>7.3f}  {idf:>6.3f}  {'YES' if ok else 'no'}")

print(f"\n保留词: {kept}")

# 对若干候选文档，逐词计算贡献
print("\n" + "=" * 68)
targets = ["低血糖症", "便秘", "蛋白尿", "糖尿病", "尿路感染"]
doc_id_by_name = {v: k for k, v in docs.items()}
print(f"{'doc':<14}" + "".join(f"{t:>9}" for t in kept) + f"{'TOTAL':>10}")
print("=" * 68)
for name in targets:
    did = doc_id_by_name.get(name)
    if did is None:
        continue
    idx = bm25._doc_ids.index(f"doc{did}_chunk0")
    tf_map = bm25._tf[idx]
    dl = bm25._dl[idx]
    row = []
    total = 0.0
    for t in kept:
        idf = bm25._idf.get(t, 0)
        f = tf_map.get(t, 0)
        if f == 0 or idf is None:
            row.append(0.0)
            continue
        denom = f + 1.5 * (1 - 0.75 + 0.75 * (dl / bm25._avgdl))
        boost = 1.6 if (len(t) == 2 and "\u4e00" <= t[0] <= "\u9fff") else 1.0
        contrib = boost * idf * (f * 2.5) / denom
        row.append(contrib)
        total += contrib
    print(f"{name:<14}" + "".join(f"{v:>9.2f}" for v in row) + f"{total:>10.2f}")
