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


def _extract_keywords(query: str) -> List[str]:
    """从查询中提取关键词（中文 bigram + 英文单词），用于词法重叠统计。"""
    kws: List[str] = []
    for m in re.findall(r"[a-zA-Z]+", query):
        if len(m) >= 2:
            kws.append(m.lower())
    for seg in re.findall(r"[\u4e00-\u9fff]+", query):
        for i in range(len(seg) - 1):
            kws.append(seg[i : i + 2])
        for ch in seg:
            kws.append(ch)
    return list(set(kws))


def _chunk_tokens(text: str) -> set[str]:
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

    # ---- 可插拔真实模型（环境具备时启用）----
    def load_model(self, model_path: str) -> bool:
        """
        加载真实 Cross-Encoder 重排模型（如 BAAI/bge-reranker-v2-m3）。
        加载成功后 rerank 将改走模型交互打分，相关性更强。
        返回是否加载成功。
        """
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            self._model = CrossEncoder(model_path)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[Reranker] 真实 Cross-Encoder 加载失败，回退融合打分: {e}")
            self._model = None
            return False

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
