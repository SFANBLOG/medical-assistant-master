"""
文档切分器：章节感知 + 句子级滑窗。

切分链路（本地 PDF / Word / Markdown 等同样适用）：
    原始文本
      -> 逐行识别标题，按标题层级切成「章节」
      -> 章节内部按句子聚合到 CHUNK_SIZE
      -> 相邻 chunk 之间用「整句」做重叠（不再按字符硬截断，避免把词切开）
      -> 可选把章节路径作为前缀写入 chunk（提升检索与生成时的上下文完整性）

- CHUNK_SIZE：每个 chunk 的目标字符数（默认 500）
- CHUNK_OVERLAP：相邻 chunk 之间的重叠字符数（默认 80，按整句回填）
- CHUNK_HEADING_PREFIX：是否把章节路径拼到 chunk 文本前（默认开启）
"""
import re
from dataclasses import dataclass

from backend import config


@dataclass
class Chunk:
    """一个文本切分块。"""
    index: int        # chunk 在文档中的序号
    text: str         # chunk 文本内容（可能含章节路径前缀）
    start: int        # 起始字符位置（近似）
    heading: str = ""  # 所属章节路径，如「第3章 糖尿病 > 3.1 分型」


def _split_by_sentence(text: str) -> list[str]:
    """按中英文标点切句（保留标点）。"""
    # 中文句号、问号、叹号、分号 + 英文对应
    parts = re.split(r"(?<=[。！？；\n.!?;])", text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# 标题识别
# ---------------------------------------------------------------------------
# (level, pattern)：level 越小层级越高；markdown 的 level 由 '#' 个数决定
_HEADING_PATTERNS: list[tuple[int, re.Pattern]] = [
    # Markdown：「# 标题」/「## 标题」
    (0, re.compile(r"^\s*(#{1,6})\s+(.+?)\s*#*\s*$")),
    # 第X章 / 第X节 / 第X篇
    (1, re.compile(r"^\s*第\s*[0-9一二三四五六七八九十百千]+\s*[章节篇部]\s*[:：、.\s]?\s*(.*)$")),
    # 一、概述 / 二、
    (2, re.compile(r"^\s*[一二三四五六七八九十]{1,3}\s*[、.．]\s*(.+)$")),
    # （一）概述
    (2, re.compile(r"^\s*[（(]\s*[一二三四五六七八九十]{1,3}\s*[)）]\s*(.*)$")),
    # 1.2.3 小节 / 1.2 小节
    (3, re.compile(r"^\s*[0-9]{1,2}(?:\.[0-9]{1,2}){1,3}\s*[:：、.\s]\s*(.*)$")),
    # （1）要点 / (1) 要点
    (3, re.compile(r"^\s*[（(]\s*[0-9]{1,2}\s*[)）]\s*(.*)$")),
    # 1、要点 / 1. 要点（排除 "2023.5" 之类数字串）
    (3, re.compile(r"^\s*[0-9]{1,2}\s*[、.．]\s*(?![0-9])\s*(.+)$")),
]

# 非 markdown 标题的最大长度：超过则认为是正文段落
_MAX_HEADING_LEN = 40


def _match_heading(line: str) -> tuple[int, str] | None:
    """
    判断一行是否为标题，返回 (level, title)；不是标题返回 None。

    注意：编号型标题（1.2 / （一）等）必须与正文在同一行且较短，
    否则会把「1. 患者男，45岁……」这类长段落误判为标题。
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 200:
        return None

    for level, pattern in _HEADING_PATTERNS:
        m = pattern.match(stripped)
        if not m:
            continue

        if level == 0:  # markdown
            hashes, title = m.group(1), m.group(2).strip()
            if not title:
                return None
            return len(hashes), title

        # 编号型标题保留完整行（含「第3章」「3.1」等编号），更利于检索与溯源
        if len(stripped) <= _MAX_HEADING_LEN:
            return level, stripped
        return None

    return None


def split_sections(text: str) -> list[tuple[str, str]]:
    """
    按标题把文档切成章节，返回 [(heading_path, body)]。

    heading_path 为从高层到低层的路径，如「第3章 糖尿病 > 3.1 分型」；
    文档开头没有标题时，路径为空字符串。
    """
    if not text or not text.strip():
        return []

    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []  # (level, title)
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            body = "\n".join(buffer).strip()
            if body:
                path = " > ".join(t for _, t in stack)
                sections.append((path, body))
            buffer.clear()

    for line in text.splitlines():
        hit = _match_heading(line)
        if hit:
            flush()
            level, title = hit
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
        else:
            buffer.append(line)

    flush()

    # 全文没有识别出任何标题：作为单一章节处理
    if not sections and text.strip():
        sections = [("", text.strip())]
    return sections


def _pack_sentences(body: str, size: int, overlap: int) -> list[str]:
    """在单个章节内按句子聚合到 size，块间用整句做 overlap。"""
    sentences = _split_by_sentence(body)
    if not sentences:
        return []

    out: list[str] = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        # 超长单句（表格行、无标点长段落）：按定长硬切
        if len(sent) > size:
            if current:
                out.append("".join(current))
                current, current_len = [], 0
            step = max(1, size - overlap)
            for i in range(0, len(sent), step):
                piece = sent[i:i + size].strip()
                if piece:
                    out.append(piece)
            continue

        if current_len + len(sent) <= size:
            current.append(sent)
            current_len += len(sent)
            continue

        # 当前块已满：产出，并用尾部整句做重叠
        out.append("".join(current))
        tail: list[str] = []
        tail_len = 0
        if overlap > 0:
            for s in reversed(current):
                if tail_len + len(s) > overlap:
                    break
                tail.insert(0, s)
                tail_len += len(s)
        current = tail + [sent]
        current_len = tail_len + len(sent)

    if current:
        out.append("".join(current))

    return [c for c in out if c.strip()]


def chunk_text(
    text: str,
    chunk_size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
    heading_prefix: bool | None = None,
) -> list[Chunk]:
    """
    将文本切分为带章节上下文的 chunk。

    策略：
    1. 按标题切章节（split_sections）；
    2. 章节内部按句子聚合到 chunk_size，块间用尾部整句重叠（不破坏词边界）；
    3. 过短的小节与相邻小节合并，直到接近 chunk_size，避免产生 50 字的碎片块；
    4. 每个小节的章节路径写在正文前（config.CHUNK_HEADING_PREFIX 控制）。

    返回 Chunk 列表。
    """
    if heading_prefix is None:
        heading_prefix = getattr(config, "CHUNK_HEADING_PREFIX", True)

    sections = split_sections(text)
    if not sections:
        return []

    # 小节的「带路径文本块」：(path, piece)
    units: list[tuple[str, str]] = []
    for path, body in sections:
        for piece in _pack_sentences(body, chunk_size, overlap):
            units.append((path, piece))

    # 贪心打包：装到接近 chunk_size 就产出，避免碎片块
    target = max(1, int(chunk_size * 0.8))
    chunks: list[Chunk] = []
    idx = 0
    cursor = 0
    buffer: list[tuple[str, str]] = []
    buffer_len = 0

    def flush() -> None:
        nonlocal idx, cursor, buffer, buffer_len
        if not buffer:
            return
        lines: list[str] = []
        last_path = None
        for path, piece in buffer:
            if heading_prefix and path and path != last_path:
                lines.append(path)
            lines.append(piece)
            last_path = path
        paths = [p for p, _ in buffer if p]
        heading = paths[0] if paths else ""
        content = "\n".join(lines)
        chunks.append(Chunk(index=idx, text=content, start=cursor, heading=heading))
        idx += 1
        cursor += sum(len(piece) for _, piece in buffer)
        buffer, buffer_len = [], 0

    for path, piece in units:
        if buffer and buffer_len + len(piece) > chunk_size:
            flush()
        buffer.append((path, piece))
        buffer_len += len(piece)
        if buffer_len >= target:
            flush()
    flush()

    return chunks


def chunk_document(text: str) -> list[Chunk]:
    """对外暴露的文档切分入口。"""
    return chunk_text(text)
