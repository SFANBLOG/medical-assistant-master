"""
文档切分器：将长文本按固定 token 数量切分为重叠的 chunk。

- CHUNK_SIZE：每个 chunk 的最大字符数（默认 500）
- CHUNK_OVERLAP：相邻 chunk 之间的重叠字符数（默认 80）
"""
import re
from dataclasses import dataclass

from backend import config
@dataclass
class Chunk:
    """一个文本切分块。"""
    index: int        # chunk 在文档中的序号
    text: str         # chunk 文本内容
    start: int        # 起始字符位置


def _split_by_sentence(text: str) -> list[str]:
    """按中英文标点切句。"""
    # 中文句号、问号、叹号、分号 + 英文对应
    parts = re.split(r"(?<=[。！？；\n.!?;])", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(
    text: str,
    chunk_size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    将文本切分为重叠的 chunk。

    策略：
    1. 先按句子切分；
    2. 按句子逐步组装，每达到 chunk_size 就产出一个 chunk；
    3. 下一个 chunk 从上一个 chunk 的尾部 overlap 处开始。

    返回 Chunk 列表。
    """
    if not text or not text.strip():
        return []

    sentences = _split_by_sentence(text)
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_len = 0
    chunk_idx = 0
    char_cursor = 0  # 原文中的全局位置（近似）

    for sent in sentences:
        sent_len = len(sent)

        if current_len + sent_len <= chunk_size:
            # 当前 chunk 还能容纳这句
            current_parts.append(sent)
            current_len += sent_len
        else:
            # 当前 chunk 已满，产出
            if current_parts:
                chunk_str = "".join(current_parts)
                chunks.append(Chunk(
                    index=chunk_idx,
                    text=chunk_str,
                    start=char_cursor,
                ))
                chunk_idx += 1
                char_cursor += len(chunk_str) - overlap if overlap < len(chunk_str) else 0

                # 计算重叠部分：从尾部取 overlap 个字符的句子
                if overlap > 0:
                    overlap_text = chunk_str[-overlap:] if len(chunk_str) > overlap else chunk_str
                    current_parts = [overlap_text]
                    current_len = len(overlap_text)
                else:
                    current_parts = []
                    current_len = 0

            # 处理超长单句（句子本身 > chunk_size）
            if sent_len > chunk_size:
                # 硬切分
                for i in range(0, sent_len, chunk_size - overlap):
                    piece = sent[i:i + chunk_size]
                    if len(piece) > overlap or i + chunk_size >= sent_len:
                        chunks.append(Chunk(
                            index=chunk_idx,
                            text=piece,
                            start=char_cursor + i,
                        ))
                        chunk_idx += 1
                current_parts = []
                current_len = 0
            else:
                current_parts.append(sent)
                current_len += sent_len

    # 最后一个 chunk
    if current_parts:
        chunk_str = "".join(current_parts)
        if chunk_str.strip():
            chunks.append(Chunk(
                index=chunk_idx,
                text=chunk_str,
                start=char_cursor,
            ))

    return chunks


def chunk_document(text: str) -> list[Chunk]:
    """对外暴露的文档切分入口。"""
    return chunk_text(text)
