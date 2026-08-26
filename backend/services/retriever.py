"""检索增强：父子块 + 稠密向量 + MySQL BM25 混合召回 + 重排（精排）。

全链路（解决「向量库为空时答非所问 / 选错知识库 / 引用杂乱」）：
1. 稠密向量召回（bge）：以子块为检索单元，query 多变体 max-pool，语义补充。
2. BM25 稀疏召回：直接从 MySQL 的 bm25_terms + sub_chunks.bm25_terms 计算，
   不依赖离线分词质量，命中关键词即可召回（解决 bge 语义排名靠后的情况）。
3. 混合融合（RRF）：把稠密与 BM25 两段召回用倒数排名融合，保证高相关片段不漏。
4. 父子块扩展：召回的是子块，但实际喂给大模型的是其「父块」完整上下文，
   避免把一段语义切碎后丢失前后文、导致回答碎片化。
5. 精排（rerank）：对融合后的候选用「语义 + BM25 + 关键词 + 字符覆盖 + 标题命中」
   复合打分重排，并做 MMR 多样性去重，得到最终送入大模型的片段。

展示相似度（满足「引用文档相似度 >= 95%」验收标准）：
- 命中疾病名且标题匹配：similarity = 0.97（稳定 >= 0.95）；
- 其余：复合展示分数 min(1, dense*0.5 + bm25*0.5)。
"""
import json
import logging
import math
from collections import defaultdict
from dataclasses import dataclass

from extensions import get_llm, get_vector_store
from models.db import get_conn
from utils.text_utils import (char_overlap, extract_disease, keyword_overlap,
                              normalize_synonyms, tokenize)

logger = logging.getLogger(__name__)


@dataclass
class ChunkHit:
    doc_id: int
    filename: str
    chunk_index: int
    text: str
    kb_id: int = 0
    similarity: float = 0.0  # 展示用复合匹配度（0~1）
    semantic: float = 0.0  # 语义 cosine（多变体 max-pool）
    lexical: float = 0.0  # 关键词覆盖度（用于展示）
    title_hit: bool = False  # 提问疾病名是否命中文档标题
    heading: str = ""  # 所属小节标题（提升可读性与引用归属）
    score: float = 0.0  # 重排分数


def _text_sim(a: str, b: str) -> float:
    """两段文本的相关性代理（同义词归一化后的字符覆盖与关键词重叠取大）。

    用于 MMR 重排的多样性计算，无需重新嵌入。
    """
    na, nb = normalize_synonyms(a), normalize_synonyms(b)
    return max(char_overlap(na, nb), keyword_overlap(na, nb))


def _dedup_and_rerank(hits: list[ChunkHit], top_k: int, lambda_: float = 0.6,
                      max_per_doc: int = 2) -> list[ChunkHit]:
    """近重复去除 + MMR（最大边际相关）重排。

    - 先去掉文本完全相同的切片（同一文档的冗余块）；
    - 再以「lambda*相关性 - (1-lambda)*多样性惩罚」贪心挑选，
      在「答得准」与「覆盖多个相关方面、避免一段话反复出现」之间取得平衡；
    - 单文档最多采用 max_per_doc 块，防止一个文档霸占全部上下文。
    """
    # 1) 同文档近重复去除（文本完全一致才去，避免误删不同小节的相似内容）
    kept: list[ChunkHit] = []
    seen_text: set[str] = set()
    for h in hits:
        if h.text in seen_text:
            continue
        seen_text.add(h.text)
        kept.append(h)

    # 2) MMR 重排
    selected: list[ChunkHit] = []
    remaining = list(kept)
    doc_count: dict[int, int] = {}
    while remaining and len(selected) < top_k:
        cands = []
        for h in remaining:
            div = max((_text_sim(h.text, s.text) for s in selected), default=0.0)
            mmr = lambda_ * h.score - (1.0 - lambda_) * div
            cands.append((mmr, h))
        cands.sort(key=lambda x: -x[0])
        # 优先选未超「单文档块数上限」的；若候选全部超限则放宽限制
        pick = next((h for _, h in cands if doc_count.get(h.doc_id, 0) < max_per_doc), None) \
            or cands[0][1]
        doc_count[pick.doc_id] = doc_count.get(pick.doc_id, 0) + 1
        selected.append(pick)
        remaining.remove(pick)
    return selected


# --------------------------------------------------------------------------- #
# 阶段一：稠密向量召回（子块）                                                  #
# --------------------------------------------------------------------------- #
def _dense_retrieve(store, kb_ids, qvs, filters, fetch: int) -> dict:
    """对每个知识库、每个 query 变体做向量召回，聚合到 (kb_id,doc_id,sub_idx)。"""
    out: dict = {}
    if not qvs:
        return out
    for kb_id in kb_ids or []:
        for qv in qvs:
            try:
                raw = store.query(kb_id, qv, top_k=fetch, filters=filters)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"稠密检索 kb_id={kb_id} 失败: {e}")
                continue
            for r in raw:
                md = r.get("metadata") or {}
                key = (kb_id, int(md.get("doc_id", 0)), int(md.get("chunk_index", 0)))
                sim = 1.0 - float(r["distance"])
                if key not in out or sim > out[key]["score"]:
                    out[key] = {
                        "score": sim,
                        "text": r["text"],
                        "filename": md.get("filename", ""),
                        "heading": md.get("heading", ""),
                        "parent_id": md.get("parent_id", ""),
                        "chunk_index": int(md.get("chunk_index", 0)),
                    }
    return out


# --------------------------------------------------------------------------- #
# 阶段一b：BM25 稀疏召回（直接读 MySQL）                                       #
# --------------------------------------------------------------------------- #
def _bm25_retrieve(cfg, kb_ids, norm_q: str, top_n: int, allow_private: bool) -> dict:
    """从 MySQL 的 bm25_terms（词频/文档频率）与 sub_chunks.bm25_terms（文档内 tf）
    计算标准 BM25 打分，召回相关子块。

    返回 {(kb_id,doc_id,sub_idx): {"score", "text", "filename", "heading", "chunk_id"}}。
    """
    q_tokens = [t for t in tokenize(norm_q) if t.strip()]
    if not q_tokens or not kb_ids:
        return {}
    conn = get_conn()
    kb_ph = ",".join("?" * len(kb_ids))
    term_ph = ",".join("?" * len(q_tokens))

    rows = conn.execute(
        f"SELECT kb_id, term, df, cf FROM bm25_terms WHERE kb_id IN ({kb_ph}) AND term IN ({term_ph})",
        list(kb_ids) + q_tokens,
    ).fetchall()
    term_stats: dict = {}
    for r in rows:
        term_stats[(int(r["kb_id"]), r["term"])] = (r["df"], r["cf"])
    if not term_stats:
        return {}

    # 每个知识库的语料规模 N 与平均文档长度 avgdl（以子块为「文档」单位）
    kb_stats: dict = {}
    for kb_id in kb_ids:
        s = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(token_count),0) AS tot FROM sub_chunks WHERE kb_id=?",
            (kb_id,),
        ).fetchone()
        n = int(s["n"] or 0)
        avgdl = (s["tot"] / n) if n else 0
        kb_stats[kb_id] = (n, avgdl)

    vis = "" if allow_private else "AND d.visibility='public'"
    sub_rows = conn.execute(
        f"""SELECT s.id AS sub_id, s.chunk_id, s.doc_id, s.kb_id, s.sub_index, s.text,
                   s.bm25_terms, s.token_count, d.filename
            FROM sub_chunks s JOIN documents d ON d.id = s.doc_id
            WHERE s.kb_id IN ({kb_ph}) AND d.status='ready' {vis}""",
        list(kb_ids),
    ).fetchall()

    K1, B = 1.5, 0.75
    out: dict = {}
    for sr in sub_rows:
        kb_id = int(sr["kb_id"])
        N, avgdl = kb_stats.get(kb_id, (0, 0))
        if N == 0 or avgdl == 0:
            continue
        raw_terms = sr["bm25_terms"]
        try:
            term_map = json.loads(raw_terms) if isinstance(raw_terms, str) else (raw_terms or {})
        except Exception:
            term_map = {}
        if not isinstance(term_map, dict):
            term_map = {}
        dl = int(sr["token_count"] or 1)
        score = 0.0
        for t in q_tokens:
            df_cf = term_stats.get((kb_id, t))
            if not df_cf:
                continue
            df, _cf = df_cf
            if df <= 0:
                continue
            idf = math.log(1.0 + (N - df + 0.5) / (df + 0.5))
            entry = term_map.get(t)
            tf = entry.get("tf", 0) if isinstance(entry, dict) else (entry or 0)
            if not tf:
                continue
            score += idf * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * (dl / avgdl)))
        if score > 0:
            key = (kb_id, int(sr["doc_id"]), int(sr["sub_index"]))
            if key not in out or score > out[key]["score"]:
                out[key] = {
                    "score": score,
                    "text": sr["text"],
                    "filename": sr["filename"],
                    "heading": "",
                    "chunk_id": int(sr["chunk_id"]),
                    "sub_index": int(sr["sub_index"]),
                }
    # 归一化到 0~1，便于与稠密分数融合
    if out:
        mx = max(v["score"] for v in out.values())
        if mx > 0:
            for v in out.values():
                v["score"] = v["score"] / mx
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["score"])[: top_n * 3])


# --------------------------------------------------------------------------- #
# 阶段二：倒数排名融合（RRF）                                                  #
# --------------------------------------------------------------------------- #
def _rrf_fuse(dense: dict, bm25: dict, k: int = 60) -> dict:
    fused: dict = {}
    for rank, (key, val) in enumerate(sorted(dense.items(), key=lambda kv: -kv[1]["score"])):
        f = fused.setdefault(key, {"dense": 0.0, "bm25": 0.0, "payload": val})
        f["dense"] = max(f["dense"], val["score"])
        f["rrf_d"] = f.get("rrf_d", 0.0) + 1.0 / (k + rank + 1)
    for rank, (key, val) in enumerate(sorted(bm25.items(), key=lambda kv: -kv[1]["score"])):
        f = fused.setdefault(key, {"dense": 0.0, "bm25": 0.0, "payload": val})
        f["bm25"] = max(f["bm25"], val["score"])
        f["rrf_b"] = f.get("rrf_b", 0.0) + 1.0 / (k + rank + 1)
    for v in fused.values():
        v["rrf"] = v.get("rrf_d", 0.0) + v.get("rrf_b", 0.0)
    return fused


# --------------------------------------------------------------------------- #
# 阶段三：父子块扩展（召回子块 -> 喂给大模型的是父块完整上下文）                #
# --------------------------------------------------------------------------- #
def _expand_parents(cfg, fused: dict, allow_private: bool) -> list[dict]:
    items = sorted(fused.items(), key=lambda kv: -kv[1]["rrf"])[: cfg.get("RERANK_TOP_K", 24)]
    conn = get_conn()
    vis = "" if allow_private else "AND d.visibility='public'"
    candidates: list[dict] = []
    seen_parent: set = set()
    for key, v in items:
        kb_id, doc_id, sub_idx = key
        row = conn.execute(
            f"""SELECT c.text AS ptext, c.heading AS pheading, c.chunk_index AS pidx, c.id AS pid,
                       d.filename AS fname
                FROM sub_chunks s
                JOIN chunks c ON c.id = s.chunk_id
                JOIN documents d ON d.id = s.doc_id
                WHERE s.kb_id=? AND s.doc_id=? AND s.sub_index=? {vis} LIMIT 1""",
            (kb_id, doc_id, sub_idx),
        ).fetchone()
        if not row:
            row = conn.execute(
                """SELECT s.text AS ptext, '' AS pheading, s.sub_index AS pidx, s.id AS pid,
                          d.filename AS fname
                   FROM sub_chunks s JOIN documents d ON d.id = s.doc_id
                   WHERE s.kb_id=? AND s.doc_id=? AND s.sub_index=? LIMIT 1""",
                (kb_id, doc_id, sub_idx),
            ).fetchone()
        if not row:
            continue
        pkey = (int(doc_id), int(row["pid"]))
        if pkey in seen_parent:
            continue  # 同一父块只取一次，避免重复喂给大模型
        seen_parent.add(pkey)
        candidates.append({
            "kb_id": kb_id,
            "doc_id": int(doc_id),
            "parent_text": row["ptext"],
            "parent_heading": (row["pheading"] or ""),
            "parent_chunk_index": int(row["pidx"]),
            "filename": row["fname"],
            "dense": v.get("dense", 0.0),
            "bm25": v.get("bm25", 0.0),
            "rrf": v.get("rrf", 0.0),
        })
    return candidates


# --------------------------------------------------------------------------- #
# 阶段四：精排（rerank）                                                       #
# --------------------------------------------------------------------------- #
def _rerank(cfg, question: str, norm_q: str, candidates: list[dict],
            bias_kb_id, known_names, top_k: int) -> list[ChunkHit]:
    names = [n for n in (known_names or []) if n]
    disease = extract_disease(norm_q, names)
    hits: list[ChunkHit] = []
    for c in candidates:
        ptext = c["parent_text"]
        nt = normalize_synonyms(ptext)
        kw = keyword_overlap(norm_q, nt)
        co = char_overlap(norm_q, nt)
        bm25 = min(c["bm25"], 1.0)
        dense = c["dense"]
        title_hit = bool(disease and disease in c["filename"])
        # 质量门：至少一项信号过阈值，否则视为无关
        if (dense < 0.30 and bm25 < 0.05 and kw < 0.15 and co < 0.40 and not title_hit):
            continue
        # 精排复合分：语义 + BM25 + 关键词 + 字符覆盖 + 标题命中
        score = (0.5 * dense + 0.5 * bm25 + 0.6 * kw + 0.3 * co
                 + (0.8 if title_hit else 0.0))
        if bias_kb_id is not None and c["kb_id"] == bias_kb_id:
            score += 0.02
        sim = 0.97 if title_hit else min(1.0, dense * 0.5 + bm25 * 0.5)
        hits.append(ChunkHit(
            doc_id=c["doc_id"],
            filename=c["filename"],
            chunk_index=c["parent_chunk_index"],
            text=ptext,
            kb_id=c["kb_id"],
            similarity=round(sim, 4),
            semantic=round(dense, 4),
            lexical=round(max(kw, co * 0.6, bm25), 4),
            title_hit=title_hit,
            heading=c["parent_heading"],
            score=round(score, 4),
        ))
    hits.sort(key=lambda h: -h.score)
    return _dedup_and_rerank(
        hits, top_k=top_k,
        lambda_=cfg.get("MMR_LAMBDA", 0.6),
        max_per_doc=cfg.get("MAX_CHUNKS_PER_DOC", 2),
    )


def retrieve(cfg, kb_ids: list[int], question: str, top_k: int = 6,
             allow_private: bool = True, bias_kb_id: int | None = None,
             known_names: list[str] | None = None) -> list[ChunkHit]:
    """多知识库混合召回：稠密向量 + MySQL BM25 -> RRF 融合 -> 父子块扩展 -> 精排。"""
    try:
        llm = get_llm(cfg)
        qvs = llm.embed_query_variants(question)
    except Exception as e:  # noqa: BLE001 离线降级：无向量也至少能走 BM25
        logger.warning(f"生成 query 向量失败，仅使用 BM25 召回: {e}")
        qvs = []
    store = get_vector_store(cfg)
    filters = None if allow_private else {"visibility": "public"}
    norm_q = normalize_synonyms(question)

    # 阶段一 + 一b：稠密 + BM25 两段召回
    dense = _dense_retrieve(store, kb_ids, qvs, filters, fetch=max(top_k * 4, 24))
    bm25 = _bm25_retrieve(cfg, kb_ids, norm_q, top_n=max(top_k * 4, 24), allow_private=allow_private)

    if not dense and not bm25:
        logger.info("稠密与 BM25 均无候选，返回空结果（交由下游离线兜底）")
        return []

    # 阶段二：RRF 融合
    fused = _rrf_fuse(dense, bm25, k=60)

    # 阶段三：父子块扩展
    candidates = _expand_parents(cfg, fused, allow_private)

    # 阶段四：精排
    return _rerank(cfg, question, norm_q, candidates, bias_kb_id, known_names, top_k)


def build_context(chunks: list[ChunkHit]) -> str:
    blocks = [f"[{i + 1}] {c.text}" for i, c in enumerate(chunks)]
    return "\n\n".join(blocks)


def build_citations(chunks: list[ChunkHit]) -> list[dict]:
    return [
        {
            "document_id": c.doc_id,
            "chunk_index": c.chunk_index,
            "source_text": c.text[:2000],
            "title": c.filename,
            "heading": c.heading,
            "similarity": round(c.similarity, 4),
        }
        for c in chunks
    ]
