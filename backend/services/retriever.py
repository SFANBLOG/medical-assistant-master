"""检索增强：向量召回（cosine 相似度）+ 轻量关键词重排 + 上下文/引用构建。

相似度语义：向量存储统一返回 cosine 距离 distance（范围 [0,2]），
本模块用 similarity = 1 - distance 得到 cosine 相似度（0~1，完全一致 ≈ 1.0）。
这修正了旧实现 1/(1+distance) 压分导致的“匹配上但分数只有 0.3~0.5”的问题。
"""
from dataclasses import dataclass

from extensions import get_llm, get_vector_store
from utils.text_utils import keyword_overlap


@dataclass
class ChunkHit:
    doc_id: int
    filename: str
    chunk_index: int
    text: str
    similarity: float = 0.0
    keyword: float = 0.0
    score: float = 0.0


def _to_similarity(distance: float) -> float:
    """cosine 距离 -> cosine 相似度，并裁剪到 [0, 1]。"""
    sim = 1.0 - distance
    return max(0.0, min(1.0, sim))


def retrieve(cfg, kb_id: int, question: str, top_k: int = 5, alpha: float = 0.2,
             allow_private: bool = True) -> list[ChunkHit]:
    """召回 top_k 片段并重排。over-fetch 后按 相似度 + α*关键词重叠 排序。

    allow_private=False 时仅保留公开文档片段（患者/群众/护士查询使用），
    确保普通用户只能检索到公开文档；过滤下推到向量库（Milvus expr / numpy 标量过滤）。
    """
    llm = get_llm(cfg)
    qv = llm.embed([question], query=True)[0]
    store = get_vector_store(cfg)
    filters = None if allow_private else {"visibility": "public"}
    raw = store.query(kb_id, qv, top_k=max(top_k, 10), filters=filters)

    hits: list[ChunkHit] = []
    for r in raw:
        sim = _to_similarity(r["distance"])
        kw = keyword_overlap(question, r["text"])
        hits.append(
            ChunkHit(
                doc_id=int(r["metadata"]["doc_id"]),
                filename=r["metadata"].get("filename", ""),
                chunk_index=int(r["metadata"].get("chunk_index", 0)),
                text=r["text"],
                similarity=sim,
                keyword=kw,
                score=sim + alpha * kw,
            )
        )
    hits.sort(key=lambda h: -h.score)
    return hits[:top_k]


def build_context(chunks: list[ChunkHit]) -> str:
    """把片段组织成带编号的参考上下文，供提示词使用。"""
    blocks = [f"[{i + 1}] {c.text}" for i, c in enumerate(chunks)]
    return "\n\n".join(blocks)


def build_citations(chunks: list[ChunkHit]) -> list[dict]:
    """构建待写入 citations 表的数据。"""
    return [
        {
            "document_id": c.doc_id,
            "chunk_index": c.chunk_index,
            "source_text": c.text[:2000],
            "title": c.filename,
            "similarity": round(c.similarity, 4),
        }
        for c in chunks
    ]
