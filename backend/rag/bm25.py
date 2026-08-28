"""
BM25 稀疏检索器（纯 Python 实现，零依赖）。

职责：在「原始文档库 → 切分后的 chunk」之上建立 Okapi BM25 倒排索引，
为混合检索提供「稀疏召回」分支。与稠密向量检索互补：
- 稠密向量擅长语义泛化（同义/上下位）
- BM25 擅长字面命中（疾病名、药名、指标名等关键词精确匹配）

对外接口：
- BM25Index.build(chunks): 用全部 chunk 构建索引
- BM25Index.search(query, kb_ids, top_k): 返回带 bm25 分数的候选列表

token 切分：中文按 单字 + bigram，英文按词（与 embedder / reranker 保持一致），
保证中英文医学关键词都能被命中。
"""
import math
import re
from typing import Optional

# Okapi BM25 超参
_K1 = 1.5
_B = 0.75


def _tokenize(text: str) -> list[str]:
    """中英文混合分词：英文单词 + 中文单字 + 中文 bigram。"""
    if not text:
        return []
    tokens: list[str] = []
    # 英文单词
    for m in re.findall(r"[a-zA-Z]+", text):
        if len(m) >= 2:
            tokens.append(m.lower())
    # 中文：单字 + bigram
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for ch in seg:
            tokens.append(ch)
        for i in range(len(seg) - 1):
            tokens.append(seg[i : i + 2])
    return tokens


class BM25Index:
    """
    内存 BM25 倒排索引。

    每个文档 = 一条 chunk（doc_id + chunk_index 唯一标识）。
    支持按 kb_ids 过滤（只检索当前角色可见知识库的 chunk）。
    """

    def __init__(self) -> None:
        # doc_id 维度：每条 chunk 一个逻辑 doc
        self._doc_ids: list[str] = []          # 逻辑 doc 顺序（与 _docs 对齐）
        self._meta: dict[str, dict] = {}        # chunk_id -> {kb_id, doc_id, chunk_index, text}
        self._tf: list[dict[str, int]] = []     # 每个 doc 的词频
        self._dl: list[int] = []                # 每个 doc 的长度（token 数）
        self._df: dict[str, int] = {}           # 词 -> 出现文档数
        self._idf: dict[str, float] = {}        # 词 -> idf
        self._avgdl: float = 0.0
        self._N: int = 0
        self._postings: dict[str, list[int]] = {}  # 词 -> 包含该词的 doc 下标列表
        self._built = False

    # ---- 构建 ----
    def build(self, chunks: list[dict]) -> None:
        """
        chunks: [{"id", "kb_id", "doc_id", "chunk_index", "text"}, ...]
        """
        self._doc_ids = []
        self._meta = {}
        self._tf = []
        self._dl = []
        self._df = {}
        self._postings = {}

        for c in chunks:
            cid = c["id"]
            text = c.get("text", "") or ""
            toks = _tokenize(text)
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            idx = len(self._doc_ids)
            self._doc_ids.append(cid)
            self._meta[cid] = {
                "kb_id": c.get("kb_id"),
                "doc_id": c.get("doc_id"),
                "chunk_index": c.get("chunk_index", 0),
                "text": text,
            }
            self._tf.append(tf)
            self._dl.append(len(toks))
            for t in tf:
                self._df[t] = self._df.get(t, 0) + 1
                self._postings.setdefault(t, []).append(idx)

        self._N = len(self._doc_ids)
        self._avgdl = (sum(self._dl) / self._N) if self._N else 0.0
        for t, dft in self._df.items():
            # Okapi IDF（加 1 避免负无穷）
            self._idf[t] = math.log((self._N - dft + 0.5) / (dft + 0.5) + 1.0)
        self._built = True

    @property
    def built(self) -> bool:
        return self._built

    def doc_count(self) -> int:
        return self._N

    # ---- 检索 ----
    def search(
        self,
        query: str,
        kb_ids: Optional[list[int]] = None,
        top_k: int = 30,
    ) -> list[dict]:
        """
        稀疏召回：对 query 计算每条 chunk 的 BM25 分数，按 kb_ids 过滤后返回 top_k。

        返回: [{"id","kb_id","doc_id","chunk_index","text","bm25"}, ...]
              bm25 为原始 BM25 分数（已非负），用于后续与稠密分数融合。
        """
        if not self._built or self._N == 0:
            return []

        kb_set = set(kb_ids) if kb_ids else None
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        # 统计 query 词频
        q_tf: dict[str, int] = {}
        for t in q_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1

        # 候选 doc 下标（出现在任一 query 词倒排表中的 doc）
        cand: set[int] = set()
        for t in q_tf:
            if t in self._postings:
                cand.update(self._postings[t])

        scores: list[tuple[int, float]] = []
        for idx in cand:
            meta = self._meta[self._doc_ids[idx]]
            if kb_set is not None and meta["kb_id"] not in kb_set:
                continue
            dl = self._dl[idx]
            tf_map = self._tf[idx]
            score = 0.0
            for t in q_tf:
                idf = self._idf.get(t)
                if idf is None:
                    continue
                f = tf_map.get(t, 0)
                if f == 0:
                    continue
                denom = f + _K1 * (1 - _B + _B * (dl / self._avgdl if self._avgdl else 1.0))
                score += idf * (f * (_K1 + 1)) / denom
            if score > 0:
                scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        top = scores[:top_k]

        out = []
        for idx, s in top:
            cid = self._doc_ids[idx]
            meta = self._meta[cid]
            out.append(
                {
                    "id": cid,
                    "kb_id": meta["kb_id"],
                    "doc_id": meta["doc_id"],
                    "chunk_index": meta["chunk_index"],
                    "text": meta["text"],
                    "bm25": round(float(s), 4),
                }
            )
        return out
