"""检索增强：向量召回 + 轻量关键词重排 + 上下文/引用构建。"""
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


def retrieve(cfg, kb_id: int, question: str, top_k: int = 5, alpha: float = 0.2) -> list[ChunkHit]:
    """召回 top_k 片段并重排。over-fetch 后按 相似度 + α*关键词重叠 排序。"""
    llm = get_llm(cfg)
    qv = llm.embed([question])[0]
    store = get_vector_store(cfg)
    raw = store.query(kb_id, qv, top_k=max(top_k, 10))

    hits: list[ChunkHit] = []
    for r in raw:
        sim = 1.0 / (1.0 + r["distance"])
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
