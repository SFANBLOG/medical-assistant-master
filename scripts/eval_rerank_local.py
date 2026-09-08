"""
本地重排 A/B 评测（自包含，不依赖 Milvus / MySQL）。

用真实的：
  - BGE 嵌入器（backend/rag/embedder，自动检测 bge-base-zh-v1.5）
  - 章节感知切分器（backend/rag/chunker，与生产播种完全一致）
  - 真实 BM25 索引（backend/rag/bm25，jieba + Okapi）
  - 真实重排器（backend/rag/reranker，融合 v3 / 可选 Cross-Encoder）

对 20 条标注医学查询：
  - 复测融合 v3 的 GT 相关度 / Hit@1 / MRR（确认 95%+ 基线）
  - 扫描 RERANK_MIN_SCORE，量化"喂给 LLM 的上下文纯净度"（回答质量）
  - 可选 --ce <model> 加载真实 Cross-Encoder，做 max-boost A/B

用法：
  python scripts/eval_rerank_local.py                 # 融合 v4 基线 + 阈值扫描（全库 241 篇）
  python scripts/eval_rerank_local.py --public-only   # 仅公开库（模拟患者提问的候选池）
  python scripts/eval_rerank_local.py --ce bge-reranker-v2-m3   # CE 增强 A/B
  python scripts/eval_rerank_local.py --only 儿童发热 糖尿病     # 只看部分查询
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import List

# ---- 必须在导入 backend 之前设置（config 在 import 时读取这些 env）----
_CE = None
_PUBLIC_ONLY = "--public-only" in sys.argv
for i, a in enumerate(sys.argv):
    if a == "--ce" and i + 1 < len(sys.argv):
        _CE = sys.argv[i + 1]
    elif a.startswith("--ce="):
        _CE = a.split("=", 1)[1]
if _CE:
    os.environ["RERANK_USE_CE"] = "true"
    os.environ["RERANK_MODEL_PATH"] = _CE if _CE not in ("1", "true", "on") else "auto"

os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("MILVUS_ENABLE", "0")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.eval_rerankers import EVAL_SET  # noqa: E402

from backend.rag.chunker import chunk_text  # noqa: E402
from backend.rag.embedder import get_embedder  # noqa: E402
from backend.rag.bm25 import BM25Index  # noqa: E402
from backend.rag.reranker import (  # noqa: E402
    CrossEncoderReranker,
    get_reranker,
    _extract_keywords,
)

try:
    from backend.rag.retriever import _expand_query as _expand
except Exception:  # noqa: BLE001
    _expand = lambda q: q  # type: ignore

UPLOADS = ROOT / "backend" / "data" / "uploads"
CHUNK_TARGET = 8  # 模拟 RERANK_TOP_K=8 的 LLM 上下文窗口


def load_chunks() -> List[dict]:
    """读取所有 md 文档，按生产切分器切块。"""
    chunks: List[dict] = []
    files = sorted(UPLOADS.rglob("*.md"))
    print(f"读取文档: {len(files)} 个 .md (public_only={_PUBLIC_ONLY})")
    for f in files:
        vis = "public" if "公开" in f.parts else "private"
        if _PUBLIC_ONLY and vis != "public":
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        if not text.strip():
            continue
        doc_stem = f.stem
        for c in chunk_text(text):
            if not c.text.strip():
                continue
            chunks.append({
                "doc_stem": doc_stem,
                "text": c.text,
                "cid": f"{doc_stem}#{c.index}",
                "vis": vis,
            })
    return chunks


def main() -> int:
    only = set()
    for i, a in enumerate(sys.argv):
        if a == "--only" and i + 1 < len(sys.argv):
            only = set(sys.argv[i + 1:])
    cases = [c for c in EVAL_SET if (not only or c["q"] in only or c["gt"] in only)]

    print("加载 BGE 嵌入器 ...")
    emb = get_embedder()
    print(f"  embedder = {type(emb).__name__}  dim={emb.dim}")

    print("切分文档 + 建 BM25 ...")
    chunks = load_chunks()
    print(f"  chunk 总数 = {len(chunks)}")

    bm25 = BM25Index()
    bm25.build([{"id": c["cid"], "doc_id": c["doc_stem"],
                 "chunk_index": 0, "text": c["text"]} for c in chunks])
    print(f"  BM25 文档数 = {bm25.doc_count()}")

    print("BGE 向量化全部 chunk（一次性）...")
    t0 = time.time()
    vecs = emb.embed_batch([c["text"] for c in chunks])
    print(f"  向量化完成 {len(vecs)} 条，耗时 {time.time()-t0:.1f}s")

    # 重排器
    if _CE:
        print(f"加载 Cross-Encoder 增强模式: {_CE}")
        rk = CrossEncoderReranker()
        print(f"  reranker = {rk.model_info}  (using_real_model={rk.using_real_model})")
        if not rk.using_real_model:
            print("  [warn] CE 未加载，将退化为纯融合（检查模型路径/依赖）")
    else:
        rk = get_reranker()

    import numpy as np
    arr = np.array(vecs, dtype="float32")

    def candidates(q: str, k: int = 30) -> List[dict]:
        qv = emb.embed(q)
        sims = arr @ qv
        dense_order = sims.argsort()[::-1][:k]
        merged = {}
        for idx in dense_order:
            c = chunks[idx]
            merged[c["cid"]] = {**c, "similarity": float(sims[idx]), "bm25": 0.0}
        try:
            for h in bm25.search(_expand(q), None, top_k=k):
                cid = h["id"]
                if cid in merged:
                    merged[cid]["bm25"] = h.get("bm25", 0.0)
                else:
                    # 由 cid 反查 chunk
                    for c in chunks:
                        if c["cid"] == cid:
                            merged[cid] = {**c, "similarity": 0.0,
                                           "bm25": h.get("bm25", 0.0)}
                            break
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] BM25 检索失败: {type(e).__name__}: {e}")
        return list(merged.values())

    def run_all():
        """对每个查询只算一次完整重排（CE 模式下避免重复调用慢模型）。"""
        per_query = []
        for case in cases:
            q = case["q"]
            cands = candidates(q)
            full = rk.rerank(q, cands, min_score=0.0, top_k=len(cands) + 1)
            per_query.append((case, full))
        return per_query

    def agg(per_query, min_score):
        hit1 = mrr = 0.0
        gt_scores: List[float] = []
        top1_scores: List[float] = []
        ctx_hit = 0           # GT 出现在 top-8（经 min_score 过滤）的比例
        ctx_leak: List[int] = []  # 每次查询 top-8 中非 GT 的条数
        n_ret: List[int] = []
        for case, full in per_query:
            gt = case["gt"]
            order = sorted(range(len(full)), key=lambda i: full[i]["score"], reverse=True)
            gt_rank = None
            gt_s = 0.0
            for r in order:
                if full[r].get("doc_stem") == gt:
                    gt_rank = r + 1
                    gt_s = full[r]["score"]
                    break
            if gt_rank is None:
                gt_scores.append(0.0)
            else:
                mrr += 1.0 / gt_rank
                if gt_rank == 1:
                    hit1 += 1
                gt_scores.append(gt_s)
            if order:
                top1_scores.append(full[order[0]]["score"])
            ctx = [x for x in full if x["score"] >= min_score][:CHUNK_TARGET]
            n_ret.append(len(ctx))
            if any(x.get("doc_stem") == gt for x in ctx):
                ctx_hit += 1
            ctx_leak.append(sum(1 for x in ctx if x.get("doc_stem") != gt))
        n = len(cases)
        return {
            "hit1": hit1 / n, "mrr": mrr / n,
            "gt": sum(gt_scores) / len(gt_scores),
            "top1": sum(top1_scores) / len(top1_scores),
            "ctx_hit": ctx_hit / n,
            "avg_leak": sum(ctx_leak) / len(ctx_leak),
            "avg_ctx": sum(n_ret) / len(n_ret),
        }

    per_query = run_all()

    print("\n" + "=" * 92)
    print(f"{'RERANK_MIN_SCORE':<18}{'Hit@1':>8}{'MRR':>8}{'GT分':>9}"
          f"{'Top1分':>9}{'GT在top8':>10}{'噪声/查询':>11}{'ctx条数':>9}")
    print("=" * 92)
    for ms in (0.30, 0.45, 0.55, 0.65):
        m = agg(per_query, ms)
        print(f"{ms:<18.2f}{m['hit1']:>7.1%}{m['mrr']:>8.3f}{m['gt']:>9.3f}"
              f"{m['top1']:>9.3f}{m['ctx_hit']:>9.1%}{m['avg_leak']:>11.2f}{m['avg_ctx']:>9.2f}")

    print("\n=== 逐查询明细（min_score=0.45）===")
    for case, full in per_query:
        gt = case["gt"]
        order = sorted(range(len(full)), key=lambda i: full[i]["score"], reverse=True)
        gt_rank = None
        gt_s = 0.0
        for r in order:
            if full[r].get("doc_stem") == gt:
                gt_rank = r + 1
                gt_s = full[r]["score"]
                break
        top1 = full[order[0]] if order else None
        top1_doc = top1.get("doc_stem") if top1 else "-"
        top1_s = top1["score"] if top1 else 0.0
        flag = "OK " if gt_rank == 1 else ("#%d" % gt_rank if gt_rank else "MISS")
        print(f"  [{flag}] GT={gt:<8} 展示相关度={gt_s:.3f}  Top1={top1_doc}({top1_s:.3f})  | {case['q']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
