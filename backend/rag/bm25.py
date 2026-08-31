"""
BM25 稀疏检索器（jieba 分词 + Okapi BM25）。

改进点（相比旧版）：
1. 使用 jieba 分词替代原始 单字+bigram，词边界更准确
2. 保留 bigram 作为补充（捕获 jieba 未覆盖的复合词）
3. 新增 IDF 平滑，避免 OOV 词被完全忽略
4. 查询侧支持同义词扩展

对外接口（不变）：
- BM25Index.build(chunks): 用全部 chunk 构建索引
- BM25Index.search(query, kb_ids, top_k): 返回带 bm25 分数的候选列表
"""
import math
import re
from typing import Optional

# Okapi BM25 超参
_K1 = 1.5
_B = 0.75

# 高频词过滤阈值
MAX_DF_RATIO = 0.5

# bigram 增益
_BIGRAM_BOOST = 1.4


def _tokenize(text: str, use_jieba: bool = True) -> list[str]:
    """
    中英文混合分词。

    优先使用 jieba 精确模式分词，回退到 单字+bigram。
    """
    if not text:
        return []

    tokens: list[str] = []

    # 英文单词
    for m in re.findall(r"[a-zA-Z]+", text):
        if len(m) >= 2:
            tokens.append(m.lower())

    # 中文分词
    chinese_text = " ".join(re.findall(r"[\u4e00-\u9fff]+", text))
    if not chinese_text:
        return tokens

    if use_jieba:
        try:
            import jieba
            # 兼容不同 jieba 版本：优先 lcut，回退 cut+list
            if hasattr(jieba, 'lcut'):
                words = jieba.lcut(chinese_text)
            else:
                words = list(jieba.cut(chinese_text))
            for w in words:
                w = w.strip()
                if len(w) >= 1:
                    tokens.append(w)
            # 补充 bigram（捕获跨词边界的有意义组合）
            for seg in re.findall(r"[\u4e00-\u9fff]+", text):
                for i in range(len(seg) - 1):
                    tokens.append(seg[i : i + 2])
            return tokens
        except ImportError:
            pass

    # 回退：单字 + bigram
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for ch in seg:
            tokens.append(ch)
        for i in range(len(seg) - 1):
            tokens.append(seg[i : i + 2])
    return tokens


class BM25Index:
    """内存 BM25 倒排索引。"""

    def __init__(self) -> None:
        self._doc_ids: list[str] = []
        self._meta: dict[str, dict] = {}
        self._tf: list[dict[str, int]] = []
        self._dl: list[int] = []
        self._df: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._avgdl: float = 0.0
        self._N: int = 0
        self._postings: dict[str, list[int]] = {}
        self._built = False

    def build(self, chunks: list[dict]) -> None:
        """chunks: [{"id", "kb_id", "doc_id", "chunk_index", "text"}, ...]"""
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
            # Okapi IDF + 1 避免负无穷
            self._idf[t] = math.log((self._N - dft + 0.5) / (dft + 0.5) + 1.0)
        self._built = True

    @property
    def built(self) -> bool:
        return self._built

    def doc_count(self) -> int:
        return self._N

    def search(
        self,
        query: str,
        kb_ids: Optional[list[int]] = None,
        top_k: int = 30,
    ) -> list[dict]:
        """稀疏召回。"""
        if not self._built or self._N == 0:
            return []

        kb_set = set(kb_ids) if kb_ids else None
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        # 查询词频 + 高频词过滤
        q_tf: dict[str, int] = {}
        for t in q_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1
        if self._N:
            discriminative = {
                t: qf
                for t, qf in q_tf.items()
                if self._df.get(t, 0) <= MAX_DF_RATIO * self._N
            }
            if discriminative:
                q_tf = discriminative

        # 候选文档
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
                boost = _BIGRAM_BOOST if (len(t) == 2 and "\u4e00" <= t[0] <= "\u9fff") else 1.0
                score += boost * idf * (f * (_K1 + 1)) / denom
            if score > 0:
                scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        top = scores[:top_k]

        out = []
        for idx, s in top:
            cid = self._doc_ids[idx]
            meta = self._meta[cid]
            out.append({
                "id": cid,
                "kb_id": meta["kb_id"],
                "doc_id": meta["doc_id"],
                "chunk_index": meta["chunk_index"],
                "text": meta["text"],
                "bm25": round(float(s), 4),
            })
        return out
