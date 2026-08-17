"""文本处理：递归字符级切分 + 关键词重叠度。

中文没有空白分词，因此按「段落 -> 行 -> 句子 -> 固定字符」递归切分，
始终在字符边界断开（Python str 按码点切片，不会切裂单个汉字/字符）。
"""
import re

# 分词正则：拉丁字母/数字/下划线 + 连续汉字
WORD_RE = re.compile(r"[a-zA-Z0-9_]+")
CJK_RE = re.compile(r"[一-鿿]+")
SENT_END_RE = re.compile(r"[。！？!?；;]")
PARA_SPLIT_RE = re.compile(r"\n\s*\n")
LINE_SPLIT_RE = re.compile(r"\n")


def tokenize(text: str) -> list[str]:
    """分词：英文单词取整词；连续汉字按字符二元组切分（CJK 无空格分词，
    二元组可命中跨文档的相邻字对，显著提升离线检索相关性）。"""
    tokens: list[str] = []
    for w in WORD_RE.findall(text.lower()):
        tokens.append(w)
    for run in CJK_RE.findall(text):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i: i + 2] for i in range(len(run) - 1))
    return tokens


def keyword_overlap(question: str, text: str) -> float:
    """简单关键词重叠度，用于召回后的轻量重排加分。"""
    q_tokens = tokenize(question)
    if not q_tokens:
        return 0.0
    t_tokens = set(tokenize(text))
    hit = sum(1 for t in q_tokens if t in t_tokens)
    return hit / len(q_tokens)


def _split_sentences(paragraph: str) -> list[str]:
    """按句子结束标点切分，保留标点。"""
    parts = SENT_END_RE.split(paragraph)
    # 重新拼接标点到句子尾部
    delimiters = SENT_END_RE.findall(paragraph)
    sentences = []
    for i, part in enumerate(parts):
        if i < len(delimiters):
            sentences.append(part + delimiters[i])
        elif part.strip():
            sentences.append(part)
    return [s for s in sentences if s.strip()]


def _merge_chunks(chunks: list[str], size: int) -> list[str]:
    """把过小的片段合并到接近 size。"""
    merged: list[str] = []
    buffer = ""
    for c in chunks:
        if buffer and len(buffer) + len(c) > size:
            merged.append(buffer)
            buffer = c
        else:
            buffer += c
    if buffer:
        merged.append(buffer)
    return merged


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """递归字符级切分。返回去空白后的文本块列表。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in PARA_SPLIT_RE.split(text) if p.strip()]
    if not paragraphs:
        return []

    pieces: list[str] = []

    def push(piece: str) -> None:
        piece = piece.strip()
        if piece:
            pieces.append(piece)

    for para in paragraphs:
        if len(para) <= size:
            push(para)
            continue
        lines = [ln.strip() for ln in LINE_SPLIT_RE.split(para) if ln.strip()]
        for line in lines:
            if len(line) <= size:
                push(line)
                continue
            sentences = _split_sentences(line)
            for sent in sentences:
                if len(sent) <= size:
                    push(sent)
                    continue
                # 最后手段：固定长度按字符切分
                for i in range(0, len(sent), size):
                    push(sent[i: i + size])

    chunks = _merge_chunks(pieces, size)

    # 相邻块之间加 overlap
    if overlap > 0 and len(chunks) > 1:
        out: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:]
            out.append((prev_tail + chunks[i]).strip())
        chunks = out

    return [c for c in chunks if c.strip()]
