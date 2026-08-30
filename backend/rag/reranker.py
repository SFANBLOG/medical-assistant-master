"""
Cross-Encoder 重排器（融合式实现，零依赖）。

在混合检索的「阶段3」对候选集做精细化重排序并过滤低相关文档：
    原始文档库 → [BM25 top30 + 稠密 top30] → 合并去重 → 重排过滤 → top-3~top-5

真实 Cross-Encoder 会对 (query, doc) 拼接后用一个孪生/交互模型直接打分，
相关性判别最强但需模型与算力。本项目当前环境无 torch/sentence-transformers，
因此采用「融合打分」近似 Cross-Encoder 的相关性排序：

    score = w_dense * norm(稠密余弦)
          + w_bm25  * norm(BM25)
          + w_lex   * 词法重叠(query↔chunk 的 token 命中率)

该分数对单一分支的偏差更鲁棒：
- 稠密向量把语义相近但字面不同的片段提上来；
- BM25 把含疾病名/药名/指标名等关键词的片段提上来；
- 词法重叠进一步惩罚「仅靠泛化、字面毫不相干」的噪声。

接口保持一致，后续可直接替换为真实 Cross-Encoder 模型（见 load_model）。
"""
import re
from typing import List, Optional

from backend import config


# 中文高频虚词/泛用词：对医学检索无区分度，参与词法重叠会引入噪声。
_STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "及", "就", "都", "而", "也", "很",
    "有", "个", "我", "你", "他", "她", "它", "这", "那", "吗", "呢", "吧",
    "啊", "哦", "呀", "什么", "怎么", "怎样", "如何", "可以", "需要", "应该",
    "注意", "患者", "疾病", "问题", "情况", "时候", "因为", "所以", "但是",
    "如果", "这样", "那样", "一些", "很多", "比较", "非常", "还有", "就是",
    "请问", "我想", "帮我", "谢谢", "是否", "能否", "应该", "怎么", "为什么",
}


def _extract_keywords(query: str) -> List[str]:
    """
    提取有区分度的关键词：中文 bigram 优先，英文单词，过滤虚词。
    单字中文判别力弱，只在没有 bigram 时作为补充。
    """
    kws: List[str] = []
    for m in re.findall(r"[a-zA-Z]+", query):
        if len(m) >= 2:
            kws.append(m.lower())
    bigrams: List[str] = []
    for seg in re.findall(r"[\u4e00-\u9fff]+", query):
        for i in range(len(seg) - 1):
            bigrams.append(seg[i : i + 2])
    kws.extend(bigrams)
    # 单字仅作补充（bigram 太少时）
    if len(bigrams) < 2:
        for seg in re.findall(r"[\u4e00-\u9fff]+", query):
            for ch in seg:
                kws.append(ch)
    return [k for k in dict.fromkeys(kws) if k not in _STOPWORDS]


def _chunk_tokens(text: str) -> set[str]:
    """chunk 侧 token 集合（中文单字 + bigram + 英文词）。"""
    toks: set[str] = set()
    for m in re.findall(r"[a-zA-Z]+", text):
        if len(m) >= 2:
            toks.add(m.lower())
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for i in range(len(seg) - 1):
            toks.add(seg[i : i + 2])
        for ch in seg:
            toks.add(ch)
    return toks


def _norm(x: float) -> float:
    return 0.0 if x <= 0 else (1.0 if x >= 1 else x)


class CrossEncoderReranker:
    """
    融合式 Cross-Encoder 重排器。

    rerank(query, candidates, top_k, min_score) -> 重排并过滤后的候选列表
    candidates 中每条需包含：id / doc_id / chunk_index / text
        + similarity（稠密余弦，缺省 0）
        + bm25（稀疏分数，缺省 0）
    返回列表每条附带 score 字段（最终相关性分）。
    """

    def __init__(
        self,
        w_dense: float = config.RERANK_W_DENSE,
        w_bm25: float = config.RERANK_W_BM25,
        w_lexical: float = config.RERANK_W_LEXICAL,
    ) -> None:
        self.w_dense = w_dense
        self.w_bm25 = w_bm25
        self.w_lexical = w_lexical
        self._model = None  # 预留：真实 Cross-Encoder 模型

    def _model_score(self, query: str, text: str) -> float:
        """真实模型打分（归一化到 [0,1]）。"""
        raw = self._model.predict([(query, text)])  # type: ignore
        try:
            val = float(raw)
        except Exception:
            val = 0.0
        # 重排模型输出通常未归一化，做 sigmoid 压缩到 [0,1]
        import math

        return 1.0 / (1.0 + math.exp(-val))

    def rerank(
        self,
        query: str,
        candidates: List[dict],
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> List[dict]:
        """
        对候选集重排序并过滤低相关文档。

        Args:
            query: 用户提问
            candidates: 合并去重后的候选（含 similarity / bm25）
            top_k: 保留条数（默认 config.RERANK_TOP_K）
            min_score: 相关性下限（默认 config.RERANK_MIN_SCORE）
        返回:
            重排后的候选列表（含 score 字段），最多 top_k 条
        """
        if not candidates:
            return []

        top_k = top_k or config.RERANK_TOP_K
        min_score = min_score if min_score is not None else config.RERANK_MIN_SCORE

        # BM25 归一化基准
        bm25_vals = [float(c.get("bm25", 0.0) or 0.0) for c in candidates]
        max_bm25 = max(bm25_vals) if bm25_vals else 0.0

        q_kws = _extract_keywords(query)
        q_set = set(q_kws)

        scored: List[dict] = []
        for c in candidates:
            text = c.get("text", "") or ""
            dense = float(c.get("similarity", 0.0) or 0.0)
            bm25 = float(c.get("bm25", 0.0) or 0.0)

            if self._model is not None:
                # 真实 Cross-Encoder 路径
                final = self._model_score(query, text)
            else:
                norm_dense = _norm(dense)
                norm_bm25 = (bm25 / max_bm25) if max_bm25 > 0 else 0.0
                # 词法重叠：query 关键词在 chunk 中的命中比例
                if q_set:
                    chunk_set = _chunk_tokens(text)
                    hit = sum(1 for k in q_set if k in chunk_set)
                    lexical = hit / len(q_set)
                else:
                    lexical = 0.0
                final = (
                    self.w_dense * norm_dense
                    + self.w_bm25 * norm_bm25
                    + self.w_lexical * lexical
                )

            item = dict(c)
            item["score"] = round(float(final), 4)
            scored.append(item)

        # 过滤低相关 + 排序 + 截断
        kept = [s for s in scored if s["score"] >= min_score]
        kept.sort(key=lambda x: x["score"], reverse=True)
        return kept[:top_k]


# 便捷单例
_default_reranker: Optional[CrossEncoderReranker] = None


def get_reranker() -> CrossEncoderReranker:
    global _default_reranker
    if _default_reranker is None:
        _default_reranker = CrossEncoderReranker()
    return _default_reranker
