"""
Cross-Encoder 重排模型 A/B 评测。

对同一批带标注的医学查询，比较不同重排策略的排序质量：
  - fusion-v3          ：当前无模型融合算法（基线）
  - <model>[maxpool]   ：真实 Cross-Encoder，长文本分段取最大片段分
  - <model>[truncate]  ：真实 Cross-Encoder，长文本直接截断
  - hybrid-<model>@wX  ：CE 分数与融合分数按权重 X 组合

评测指标：
  Hit@1  正确文档排第 1 的比例
  MRR    平均倒数排名
  Top1   Top-1 文档的平均相关度分数
  GT     标注文档（ground truth）的平均得分（衡量"分数是否给够"）

用法：
    python scripts/eval_rerankers.py
    python scripts/eval_rerankers.py --only bge-reranker-base
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from pathlib import Path
from typing import Callable, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("DATABASE_NAME", "eval_rerank_tmp")
os.environ.setdefault("MILVUS_ENABLE", "0")

# ---------------------------------------------------------------------------
# 评测集：查询 -> 期望命中的文档名（backend/data/uploads/**/公开/<name>.md）
# 覆盖 9 个科室 + 5 种问句类型，全部为知识库中真实存在的文档
# ---------------------------------------------------------------------------
EVAL_SET: List[dict] = [
    {"q": "儿童发热需要立刻就医吗？", "gt": "儿童发热", "type": "when_to"},
    {"q": "小儿肺炎怎么治疗？", "gt": "小儿肺炎", "type": "how_to"},
    {"q": "小孩拉肚子该怎么办？", "gt": "小儿腹泻", "type": "how_to"},
    {"q": "手足口病有什么症状？", "gt": "手足口病", "type": "symptom"},
    {"q": "糖尿病会有哪些并发症？", "gt": "糖尿病", "type": "symptom"},
    {"q": "高血压患者饮食要注意什么？", "gt": "高血压", "type": "how_to"},
    {"q": "哮喘急性发作时怎么处理？", "gt": "支气管哮喘", "type": "how_to"},
    {"q": "什么是痛风？", "gt": "痛风", "type": "what"},
    {"q": "骨折后多久能康复？", "gt": "骨折术后康复", "type": "when_to"},
    {"q": "胃溃疡会癌变吗？", "gt": "消化性溃疡", "type": "yes_no"},
    {"q": "偏头痛怎么缓解？", "gt": "偏头痛", "type": "how_to"},
    {"q": "荨麻疹反复发作是什么原因？", "gt": "荨麻疹", "type": "what"},
    {"q": "心肌梗死发作前有什么前兆？", "gt": "心肌梗死", "type": "symptom"},
    {"q": "尿路感染吃什么药？", "gt": "尿路感染", "type": "how_to"},
    {"q": "腰椎间盘突出能自愈吗？", "gt": "腰椎间盘突出", "type": "yes_no"},
    {"q": "新生儿黄疸需要照蓝光吗？", "gt": "新生儿黄疸", "type": "yes_no"},
    {"q": "湿疹和接触性皮炎怎么区分？", "gt": "接触性皮炎", "type": "what"},
    {"q": "脑卒中急救的黄金时间是什么？", "gt": "脑卒中急救", "type": "when_to"},
    {"q": "肾结石疼起来怎么办？", "gt": "肾结石", "type": "how_to"},
    {"q": "癫痫发作时旁人该做什么？", "gt": "癫痫", "type": "how_to"},
]


def _doc_of(text: str) -> str:
    """从 chunk 文本提取文档名（格式：'文档名 > 章节\\n正文'）。"""
    head = text.split("\n", 1)[0]
    return head.split(" > ")[0].strip().lstrip("#> ").strip()


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


# ---------------------------------------------------------------------------
# 长文本处理：Cross-Encoder max_length 仅 512，整篇文档会被截断
# ---------------------------------------------------------------------------
def _split_windows(text: str, size: int, overlap: int) -> List[str]:
    if len(text) <= size:
        return [text]
    step = max(1, size - overlap)
    return [text[i:i + size] for i in range(0, len(text), step)]


class CEScorer:
    """真实 Cross-Encoder 打分器，支持长文本分段聚合。"""

    def __init__(self, path: Path, long_mode: str = "maxpool",
                 max_windows: int = 0):
        from sentence_transformers import CrossEncoder

        self.path = path
        self.long_mode = long_mode
        self.max_windows = max_windows  # 0=不限；>0 时每段文本最多取前 N 个窗口
        t0 = time.time()
        self.model = CrossEncoder(str(path))
        self.load_s = time.time() - t0
        try:
            self.max_len = int(self.model.max_length) or 512
        except Exception:  # noqa: BLE001
            self.max_len = 512

    def logits_batch(self, query: str, texts: List[str]) -> List[float]:
        """返回聚合后的原始 logit（未经 sigmoid）。"""
        win = max(120, self.max_len - len(query) - 12)
        pairs: List[tuple] = []
        spans: List[tuple] = []  # (start, end) 在展平预测列表中的切片范围
        for t in texts:
            parts = _split_windows(t, size=win, overlap=win // 5)
            if self.long_mode == "truncate":
                parts = parts[:1]
            if self.max_windows:
                parts = parts[: self.max_windows]
            spans.append((len(pairs), len(pairs) + len(parts)))
            pairs.extend((query, p) for p in parts)

        raw = self.model.predict(pairs)
        vals = [float(v) for v in raw]

        out: List[float] = []
        for s, e in spans:
            chunk = vals[s:e]
            if not chunk:
                out.append(0.0)
            elif self.long_mode == "mean":
                out.append(sum(chunk) / len(chunk))
            else:  # maxpool：取最相关片段
                out.append(max(chunk))
        return out

    def score_batch(self, query: str, texts: List[str]) -> List[float]:
        return [_sigmoid(v) for v in self.logits_batch(query, texts)]


# ---------------------------------------------------------------------------
# 检索层：dense + bm25 合并候选
# ---------------------------------------------------------------------------
class Retriever:
    def __init__(self):
        from backend.rag.embedder import get_embedder
        from backend.rag.vectorstore import get_vectorstore
        from backend.rag.reranker import get_reranker, _extract_keywords
        from backend.rag.retriever import _ensure_bm25, _expand_query

        self.emb = get_embedder()
        self.vs = get_vectorstore()
        self.fusion = get_reranker()
        self._extract_keywords = _extract_keywords
        self._expand = _expand_query
        self.bm25 = None
        try:
            self.bm25 = _ensure_bm25()
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] BM25 构建失败: {type(e).__name__}: {e}")
        self.bm25_ok = self.bm25 is not None

    def candidates(self, query: str, dense_k: int = 20, bm25_k: int = 20) -> List[dict]:
        qv = self.emb.embed(query)
        hits = self.vs.search(qv, kb_ids=[], top_k=dense_k, min_similarity=0.0)
        merged = {(h["doc_id"], h["chunk_index"]): {**h, "bm25": 0.0} for h in hits}
        if self.bm25_ok:
            try:
                for h in self.bm25.search(self._expand(query), None, top_k=bm25_k):
                    key = (h["doc_id"], h["chunk_index"])
                    v = float(h.get("bm25", 0.0) or 0.0)
                    if key in merged:
                        merged[key]["bm25"] = v
                    else:
                        merged[key] = {**h, "bm25": v}
            except Exception as e:  # noqa: BLE001
                print(f"  [warn] BM25 检索失败: {type(e).__name__}: {e}")
        return list(merged.values())

    def fusion_batch(self, query: str, cands: List[dict]) -> List[float]:
        bm25_vals = [float(c.get("bm25", 0.0) or 0.0) for c in cands]
        max_bm25 = max(bm25_vals) if bm25_vals else 0.0
        q_kws = self._extract_keywords(query)
        return [
            self.fusion._fusion_score(
                query,
                c.get("text", "") or "",
                float(c.get("similarity", 0.0) or 0.0),
                float(c.get("bm25", 0.0) or 0.0),
                max_bm25,
                q_kws,
            )
            for c in cands
        ]


# ---------------------------------------------------------------------------
# 评测主流程
# ---------------------------------------------------------------------------
def evaluate(score_batch: Callable[[str, List[str]], List[float]],
             cands_cache: dict) -> dict:
    hit1 = 0
    rr_sum = 0.0
    top1_scores: List[float] = []
    gt_scores: List[float] = []
    t0 = time.time()

    for case in EVAL_SET:
        q, gt = case["q"], case["gt"]
        texts = [c.get("text", "") or "" for c in cands_cache[q]]
        scores = score_batch(q, texts)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        ranked = [(_doc_of(texts[i]), scores[i]) for i in order]

        if ranked:
            top1_scores.append(ranked[0][1])

        for rank, (name, s) in enumerate(ranked, start=1):
            if name == gt:
                rr_sum += 1.0 / rank
                gt_scores.append(s)
                if rank == 1:
                    hit1 += 1
                break
        else:
            gt_scores.append(0.0)

    n = len(EVAL_SET)
    return {
        "hit1": hit1 / n,
        "mrr": rr_sum / n,
        "top1": (sum(top1_scores) / len(top1_scores)) if top1_scores else 0.0,
        "gt": (sum(gt_scores) / len(gt_scores)) if gt_scores else 0.0,
        "secs": time.time() - t0,
    }


def dump_logits(scorer: "CEScorer", cands_cache: dict, fusion_cache: dict,
                label: str) -> None:
    """导出 CE 原始 logit 分布，用于拟合 'logit -> 相关度百分比' 的校准曲线。"""
    import json
    import statistics

    gt_logits: List[float] = []
    top_logits: List[float] = []
    neg_logits: List[float] = []   # 排名靠后（明显不相关）的候选
    rows = []

    for case in EVAL_SET:
        q, gt = case["q"], case["gt"]
        cands = cands_cache[q]
        texts = [c.get("text", "") or "" for c in cands]
        logits = scorer.logits_batch(q, texts)
        order = sorted(range(len(logits)), key=lambda i: logits[i], reverse=True)

        gt_idx = next((i for i, t in enumerate(texts) if _doc_of(t) == gt), None)
        if gt_idx is None:
            continue
        gt_l = logits[gt_idx]
        rank = order.index(gt_idx) + 1
        gt_logits.append(gt_l)
        top_logits.append(logits[order[0]])
        # 取排名 5 名之后、且不是 GT 的候选作为负样本
        neg_logits.extend(logits[i] for i in order[4:] if i != gt_idx)

        rows.append({
            "query": q, "gt": gt, "gt_logit": round(gt_l, 3),
            "gt_rank": rank,
            "top1": _doc_of(texts[order[0]]),
            "top1_logit": round(logits[order[0]], 3),
            "max_logit": round(max(logits), 3),
            "min_logit": round(min(logits), 3),
            "median_logit": round(statistics.median(logits), 3),
        })

    def _pct(vals: List[float], p: float) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        k = (len(s) - 1) * p
        f, c = int(math.floor(k)), min(int(math.ceil(k)), len(s) - 1)
        return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)

    out = {
        "model": label,
        "n_query": len(rows),
        "rows": rows,
        "gt_logit_percentiles": {f"p{int(p*100)}": round(_pct(gt_logits, p), 3)
                                 for p in [0, .1, .25, .5, .75, .9, 1.0]},
        "neg_logit_percentiles": {f"p{int(p*100)}": round(_pct(neg_logits, p), 3)
                                  for p in [0, .1, .25, .5, .75, .9, 1.0]},
        "gt_mean": round(statistics.mean(gt_logits), 3) if gt_logits else 0,
        "neg_mean": round(statistics.mean(neg_logits), 3) if neg_logits else 0,
    }
    path = Path("scripts/logit_dump.json")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== CE 原始 logit 分布 [{label}] ===")
    print(f"GT 文档 (相关) : {out['gt_logit_percentiles']}  均值={out['gt_mean']}")
    print(f"排名5+ (不相关): {out['neg_logit_percentiles']}  均值={out['neg_mean']}")
    print(f"已导出明细 -> {path}")

    # 给出温度缩放建议：目标把 GT 中位数映射到 0.95
    gt_med = _pct(gt_logits, .5)
    print(f"\n校准建议（目标：GT 中位数 -> 0.95）")
    for T in (1.0, 2.0, 3.0, 4.0, 6.0, 8.0):
        print(f"  T={T:<4} sigmoid({gt_med:.2f}/{T}) = {_sigmoid(gt_med/T):.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--no-hybrid", action="store_true")
    ap.add_argument("--dump", default=None,
                    help="导出指定模型的原始 logit 分布到 JSON，用于拟合分数校准参数")
    ap.add_argument("--max-windows", type=int, default=0,
                    help="每段文本最多取前 N 个窗口（0=不限，调小可加速）")
    args = ap.parse_args()

    r = Retriever()
    print(f"Embedder : {type(r.emb).__name__} (dim={r.emb.dim})")
    print(f"Chunks   : {r.vs.count}")
    print(f"BM25     : {'OK' if r.bm25_ok else 'UNAVAILABLE'}")
    print(f"Fusion   : {r.fusion.model_info}")
    print(f"评测集   : {len(EVAL_SET)} 条查询")
    print()

    print("预取候选集 ...")
    cands_cache: dict = {}
    for case in EVAL_SET:
        cands_cache[case["q"]] = r.candidates(case["q"])
    avg = sum(len(v) for v in cands_cache.values()) / len(cands_cache)
    print(f"候选集平均 {avg:.1f} 条/查询\n")

    print("预计算融合分数 ...")
    fusion_cache = {q: r.fusion_batch(q, cs) for q, cs in cands_cache.items()}

    strategies: dict[str, Callable] = {"fusion-v3":
                                       lambda q, _t: fusion_cache[q]}

    # --- 真实 Cross-Encoder ---
    from backend import config
    model_dir: Path = config.MODEL_DIR
    ce: dict[str, CEScorer] = {}
    for key in ["bge-reranker-base", "bge-reranker-v2-m3", "bge-reranker-large"]:
        d = model_dir / key
        if not (d / "config.json").exists():
            print(f"[skip] {key} 未下载（{d}）")
            continue
        if args.only and key not in args.only:
            continue
        for mode in ["maxpool", "truncate"]:
            try:
                s = CEScorer(d, mode, max_windows=args.max_windows)
                ce[f"{key}[{mode}]"] = s
                print(f"[load] {key}[{mode}]  max_len={s.max_len}  {s.load_s:.1f}s")
            except Exception as e:  # noqa: BLE001
                print(f"[fail] {key}[{mode}] {type(e).__name__}: {e}")

    # --- 只导出 logit 分布（用于拟合校准）---
    if args.dump:
        scorer = ce.get(args.dump) or ce.get(f"{args.dump}[maxpool]")
        if scorer is None:
            print(f"[err ] --dump 指定的模型不可用: {args.dump}")
            return 1
        dump_logits(scorer, cands_cache, fusion_cache, args.dump)
        return 0

    for label, scorer in ce.items():
        strategies[label] = (lambda s: (lambda q, t: s.score_batch(q, t)))(scorer)
        if not args.no_hybrid and label.endswith("[maxpool]"):
            base = label[: -len("[maxpool]")]
            for w in (0.5, 0.7):
                strategies[f"hybrid-{base}@w{w}"] = (
                    lambda s, ww, fc=fusion_cache: (
                        lambda q, t: [
                            ww * a + (1 - ww) * b
                            for a, b in zip(s.score_batch(q, t), fc[q])
                        ]
                    )
                )(scorer, w)

    print()
    print("=" * 80)
    print(f"{'策略':<36}{'Hit@1':>8}{'MRR':>8}{'Top1分':>9}{'GT分':>9}{'耗时':>9}")
    print("=" * 80)

    results = []
    for name, fn in strategies.items():
        try:
            m = evaluate(fn, cands_cache)
        except Exception as e:  # noqa: BLE001
            print(f"{name:<36}  评测失败: {type(e).__name__}: {e}")
            continue
        results.append((name, m))
        print(f"{name:<36}{m['hit1']:>7.1%}{m['mrr']:>8.3f}"
              f"{m['top1']:>9.3f}{m['gt']:>9.3f}{m['secs']:>8.1f}s")

    print("=" * 80)
    if results:
        best = max(results, key=lambda x: (x[1]["mrr"], x[1]["gt"]))
        print(f"最佳(MRR) : {best[0]}  Hit@1={best[1]['hit1']:.1%}  "
              f"MRR={best[1]['mrr']:.3f}  GT分={best[1]['gt']:.3f}  Top1分={best[1]['top1']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
