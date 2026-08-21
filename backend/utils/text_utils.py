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


def keyword_overlap(question: str, text: str) -> float:
    """简单关键词重叠度，用于召回后的轻量重排加分。"""
    q_tokens = tokenize(question)
    if not q_tokens:
        return 0.0
    t_tokens = set(tokenize(text))
    hit = sum(1 for t in q_tokens if t in t_tokens)
    return hit / len(q_tokens)


def char_overlap(question: str, text: str) -> float:
    """字符级覆盖度：提问中的有效中文字符有多少出现在候选文本中（0~1）。

    中文问答中提问往往只包含几个关键实体（疾病名、症状、身体部位），
    字符级覆盖对「问题 -> 参考片段」的匹配比二元组分词更稳定，
    即使文档措辞不同，只要实体一致即可得到较高分值。
    """
    q_chars = {ch for ch in question if "\u4e00" <= ch <= "\u9fff"}
    if not q_chars:
        return 0.0
    t_chars = set(text)
    hit = sum(1 for ch in q_chars if ch in t_chars)
    return hit / len(q_chars)


# 医疗常见同义词/别称归一化：提问与文档用词不一致时统一到主词。
SYNONYMS = {
    "发烧": "发热",
    "中风": "脑卒中",
    "脑中风": "脑卒中",
    "脚气": "足癣",
    "青春痘": "痤疮",
    "牛皮癣": "银屑病",
    "上感": "上呼吸道感染",
    "肠胃炎": "胃肠炎",
    "高血压病": "高血压",
    "高血脂": "血脂异常",
}


def normalize_synonyms(text: str) -> str:
    """把常见同义词替换为主词，提升提问与文档的匹配度。"""
    for k, v in SYNONYMS.items():
        if k in text:
            text = text.replace(k, v)
    return text


def extract_disease(question: str, known_names: list[str]) -> str:
    """从提问中提取最长的已知疾病名（用于标题级强匹配）。

    known_names 传知识库文档标题（疾病名）列表即可；找不到返回空串。
    兼容带括号的标题（如“银屑病（牛皮癣）”）——括号内的别名也参与匹配。
    """
    candidates: set[str] = set()
    for name in known_names:
        name = name.strip().strip("#").strip()
        if not name or len(name) < 2:
            continue
        candidates.add(name)
        # “银屑病（牛皮癣）”“慢性阻塞性肺疾病(COPD)” -> 主名 + 括号内别名
        inner = re.findall(r"[（(]([^（）()]+)[）)]", name)
        for part in inner:
            part = part.strip()
            if len(part) >= 2:
                candidates.add(part)
        base = re.split(r"[（(]", name)[0].strip()
        if len(base) >= 2:
            candidates.add(base)
    best = ""
    for name in candidates:
        if name in question and len(name) > len(best):
            best = name
    return best


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
