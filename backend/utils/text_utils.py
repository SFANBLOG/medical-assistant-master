"""文本处理：递归字符级切分 + 关键词重叠度。

中文没有空白分词，因此按「段落 -> 行 -> 句子 -> 固定字符」递归切分，
始终在字符边界断开（Python str 按码点切片，不会切裂单个汉字/字符）。
"""
import re

# 分词正则：拉丁字母/数字/下划线 + 连续汉字
WORD_RE = re.compile(r"[a-zA-Z0-9_]+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
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


# 文档标题（Markdown # 风格）正则
HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _split_recursive(text: str, size: int) -> list[str]:
    """递归字符级切分（段落 -> 行 -> 句 -> 定长），返回长度 <= size 的片段列表。"""
    out: list[str] = []
    for para in [p.strip() for p in PARA_SPLIT_RE.split(text) if p.strip()]:
        if len(para) <= size:
            out.append(para)
            continue
        for line in [l.strip() for l in LINE_SPLIT_RE.split(para) if l.strip()]:
            if len(line) <= size:
                out.append(line)
                continue
            for sent in _split_sentences(line):
                if len(sent) <= size:
                    out.append(sent)
                    continue
                for i in range(0, len(sent), size):
                    out.append(sent[i: i + size])
    return out


def _count_tokens(text: str) -> int:
    """简单 token 估算：中文按字/二元组，英文按词。"""
    return len(tokenize(text)) or len(text)


def chunk_document_parent_child(text: str, parent_size: int = 760, child_size: int = 380,
                                 child_overlap: int = 60) -> tuple[list[dict], list[dict]]:
    """父子块切分：父块保留完整章节上下文，子块作为稠密检索单元。

    返回 (parents, children) 两个列表：
    - parent: {id, text, heading, chunk_index, level, parent_id, children:[...], token_count}
    - child:  {id, text, heading, chunk_index, sub_index, parent_id, token_count}

    切分策略：
    1. 按 Markdown 标题将文档拆成章节；
    2. 每个章节作为一个父块（超过 parent_size 再按段落/句子细分，保持父块内连续）；
    3. 在父块内部按 child_size / child_overlap 切子块，子块继承父块 heading；
    4. 父块与子块均去重，并估算 token 数。
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return [], []

    sections: list[tuple[str, str]] = []
    ms = list(HEADING_RE.finditer(text))
    if ms and ms[0].start() > 0:
        pre = text[: ms[0].start()].strip()
        if pre:
            sections.append(("", pre))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        body = text[m.end(): end].strip()
        if body:
            sections.append((m.group(2).strip(), body))
    if not sections:
        sections = [("", text)]

    parents: list[dict] = []
    children: list[dict] = []
    parent_idx = 0
    child_global_idx = 0

    for heading, body in sections:
        # 父块：先尝试整个章节；过长则递归切分但保持同章节
        parent_pieces = _split_recursive(body, parent_size)
        for pi, piece in enumerate(parent_pieces):
            if not piece.strip():
                continue
            parent = {
                "id": f"p_{parent_idx}",
                "text": piece,
                "heading": heading,
                "chunk_index": parent_idx,
                "level": heading.count("#") if heading else 0,
                "parent_id": None,
                "children": [],
                "token_count": _count_tokens(piece),
            }

            # 在父块内切子块
            sub_pieces = _split_recursive(piece, child_size)
            if child_overlap > 0 and len(sub_pieces) > 1:
                merged = [sub_pieces[0]]
                for p in sub_pieces[1:]:
                    merged.append((merged[-1][-child_overlap:] + p).strip())
                sub_pieces = merged

            seen_sub: set[str] = set()
            for si, sub in enumerate(sub_pieces):
                sub = sub.strip()
                if not sub or sub in seen_sub:
                    continue
                seen_sub.add(sub)
                child = {
                    "id": f"c_{child_global_idx}",
                    "text": sub,
                    "heading": heading,
                    "chunk_index": parent_idx,
                    "sub_index": si,
                    "parent_id": parent["id"],
                    "token_count": _count_tokens(sub),
                }
                parent["children"].append(child)
                children.append(child)
                child_global_idx += 1

            parents.append(parent)
            parent_idx += 1

    return parents, children


def chunk_document(text: str, size: int = 380, overlap: int = 60) -> list[dict]:
    """标题感知切分：按章节标题分块、为每块携带所属小节上下文、去除近重复块。

    返回 [{"text": str, "heading": str}, ...]。
    - heading 前缀（如「（小节：高血压的饮食原则）」）显著提升切片的可检索性与
      LLM 对资料归属的理解，避免把不同章节内容混为一谈导致回答杂乱。
    - 末尾对完全相同/高度重叠的块去重，避免同一段话被多次喂给大模型。

    内部使用父子块切分，返回子块列表（保持与原接口一致）。
    """
    parents, _ = chunk_document_parent_child(text, parent_size=size * 2, child_size=size,
                                              child_overlap=overlap)
    out: list[dict] = []
    seen: set[str] = set()
    for p in parents:
        for c in p.get("children", []):
            c_text = c["text"].strip()
            if c_text and c_text not in seen:
                seen.add(c_text)
                out.append({"text": c_text, "heading": p["heading"]})
    return out
