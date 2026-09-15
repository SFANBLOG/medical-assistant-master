"""
文档切分（Chunker）
==================================================================
针对中文医学文档调优：按段落 / 句子聚合，目标块长 CHUNK_SIZE（默认 500），
块间重叠 CHUNK_OVERLAP（默认 80），避免把完整语义切断，从而提升检索命中率
（修复「相似度只有 0.3~0.5」的切分层面根因）。
"""
import config as cfg


def split_text(text: str, chunk_size=None, overlap=None) -> list[str]:
    chunk_size = chunk_size or cfg.CHUNK_SIZE
    overlap = overlap or cfg.CHUNK_OVERLAP
    if overlap >= chunk_size:
        overlap = chunk_size // 4

    text = (text or "").strip()
    if not text:
        return []

    # 先按空行/标题分段，再按句断句
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    buf = ""
    for para in paragraphs:
        # 若单段已超过块长，按句进一步切
        if len(para) > chunk_size:
            sentences = _split_sentences(para)
            for sent in sentences:
                buf, chunks = _append(buf, sent, chunks, chunk_size, overlap)
        else:
            buf, chunks = _append(buf, para, chunks, chunk_size, overlap)
    if buf.strip():
        chunks.append(buf.strip())
    return [c for c in chunks if c.strip()]


def _append(buf: str, piece: str, chunks: list, chunk_size: int, overlap: int):
    if not piece:
        return buf, chunks
    if len(buf) + len(piece) + 1 <= chunk_size:
        buf = (buf + "\n" + piece).strip() if buf else piece
    else:
        if buf:
            chunks.append(buf.strip())
        # 重叠：取上一块末尾 overlap 个字符作为新块开头
        if overlap > 0 and len(buf) > overlap:
            buf = buf[-overlap:]
        else:
            buf = ""
        buf = (buf + "\n" + piece).strip() if buf else piece
    return buf, chunks


def _split_sentences(para: str) -> list[str]:
    # 中文句号、问号、感叹号、分号断句；保留标点
    parts = []
    cur = ""
    for ch in para:
        cur += ch
        if ch in "。！？；.!?;":
            parts.append(cur.strip())
            cur = ""
    if cur.strip():
        parts.append(cur.strip())
    return parts
