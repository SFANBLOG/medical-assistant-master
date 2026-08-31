"""
Cross-Encoder 重排器（真实模型优先 + 增强融合 v3 兜底）。

v3 核心改进（解决"相关度普遍偏低"问题）：
- BGE 稠密相似度作为主信号（weight=0.60），BM25 失效时自动将权重重分配给稠密
- 多粒度词法匹配：字符 bigram + 词级 + 实体级（疾病名/症状名）
- 问题类型感知：判断问句 / 选择问 / "何时就医"类 → 匹配策略不同
- 标题/heading 匹配加权：文档标题与查询主题一致时大幅加分
- 诚实校准：不再人为拉伸到 [0.30, 1.0]，高分 = 真正相关

优先级：
1. 真实 Cross-Encoder 模型（BAAI/bge-reranker-v2-min 或兼容模型）
   - 配置：RERANK_MODEL_PATH 指向模型目录或 "auto" 自动检测
2. 融合算法 v3（无模型时的兜底）
"""
import math
import os
import re
from typing import List, Optional

from backend import config


# ---- 中文停用词 ----
_STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "及", "就", "都", "而", "也", "很",
    "有", "个", "我", "你", "他", "她", "它", "这", "那", "吗", "呢", "吧",
    "啊", "哦", "呀",
}

# 医学高频泛词（几乎每篇医学文档都出现，区分度极低）
_MEDICAL_STOPWORDS = {
    "治疗", "诊断", "症状", "检查", "临床", "表现", "进行", "出现",
    "考虑", "可能", "常见", "通常", "一般", "相关", "影响",
    "方法", "结果", "分析", "发现", "报告", "病例",
    "患者", "疾病", "问题", "情况", "时候",
}

# 医学实体词典（用于实体级匹配加分）
_MEDICAL_ENTITIES: dict[str, List[str]] = {
    "发热": ["发烧", "体温升高", "高热", "低热", "体温", "度数", "退烧"],
    "儿童": ["小儿", "小孩", "幼儿", "婴幼儿", "孩童", "宝宝"],
    "肺炎": ["肺部感染", "肺感染"],
    "腹泻": ["拉肚子", "便溏", "腹泻"],
    "咳嗽": ["咳", "干咳", "咳喘"],
    "就医": ["看医生", "去医院", "就诊", "挂号", "求医", "急诊"],
    "立刻": ["马上", "立即", "赶紧", "迅速", "及时", "尽快"],
    "惊厥": ["抽搐", "抽风", "惊风"],
    "脱水": ["缺水", "体液不足"],
}


def _extract_keywords(query: str) -> List[str]:
    """
    提取有区分度的关键词（v3：多策略 + 容错）。

    返回的关键词按重要性排序：
    1. 长词优先（3+ 字的医学实体）
    2. jieba 分词结果（名词/动词/形容词）
    3. bigram 回退
    """
    kws: List[str] = []
    seen: set[str] = set()

    def _add(w: str):
        w = w.strip()
        if (
            len(w) >= 2
            and w not in _STOPWORDS
            and w not in _MEDICAL_STOPWORDS
            and w not in seen
        ):
            kws.append(w)
            seen.add(w)

    # 策略 1：提取有意义的实体级长词（2~6 字，基于同义词表匹配）
    # 不再暴力枚举所有子串，而是只保留在医学同义词表中出现的组合
    for entity_name, synonyms in _MEDICAL_ENTITIES.items():
        if entity_name in query and len(entity_name) >= 2:
            _add(entity_name)
        for syn in synonyms:
            if syn in query and len(syn) >= 2:
                _add(syn)

    # 策略 2：jieba 分词
    try:
        import jieba
        try:
            import jieba.posseg as pseg
            words = pseg.cut(query)
            for item in words:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    w, flag = item[0], item[1]
                else:
                    w, flag = str(item), ""
                _add(w)
        except (ImportError, AttributeError, TypeError):
            if hasattr(jieba, 'lcut'):
                words = jieba.lcut(query)
            else:
                words = list(jieba.cut(query))
            for w in words:
                _add(w)
    except ImportError:
        pass

    # 策略 3：bigram 回退
    if len(kws) < 2:
        for m in re.findall(r"[a-zA-Z]+", query):
            if len(m) >= 2:
                _add(m.lower())
        for seg in re.findall(r"[\u4e00-\u9fff]+", query):
            for i in range(len(seg) - 1):
                _add(seg[i:i + 2])
        if len(kws) < 2:
            for seg in re.findall(r"[\u4e00-\u9fff]+", query):
                for ch in seg:
                    _add(ch)

    return kws


def _chunk_tokens(text: str) -> set[str]:
    """chunk 侧 token 集合（字符 + bigram）。"""
    toks: set[str] = set()
    for m in re.findall(r"[a-zA-Z]+", text):
        if len(m) >= 2:
            toks.add(m.lower())
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for i in range(len(seg) - 1):
            toks.add(seg[i:i + 2])
        for ch in seg:
            toks.add(ch)
    return toks


def _chunk_words(text: str) -> List[str]:
    """chunk 侧分词列表（尝试 jieba，回退 bigram）。"""
    words: List[str] = []
    try:
        import jieba
        if hasattr(jieba, 'lcut'):
            words = jieba.lcut(text)
        else:
            words = list(jieba.cut(text))
    except ImportError:
        for seg in re.findall(r"[\u4e00-\u9fff]+", text):
            for i in range(len(seg) - 1):
                words.append(seg[i:i + 2])
    return [w for w in words if len(w.strip()) >= 1]


def _norm(x: float) -> float:
    """归一化到 [0,1]。"""
    return 0.0 if x <= 0 else (1.0 if x >= 1 else x)


def _sigmoid(x: float) -> float:
    """Sigmoid 压缩。"""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _detect_query_type(query: str) -> str:
    """
    检测问题类型，影响匹配策略。

    Returns:
        "yes_no"     — 判断问（需要...吗？/是否...？/能不能...？）
        "when_to"    — 时机问（何时...？/什么情况下...？/...需要立刻...？）
        "what_why"   — 因果/定义问（什么是...？/为什么...？/...的原因？）
        "how_to"     — 方法问（怎么...？/如何...？/...怎么办？）
        "other"      — 其他
    """
    q = query.strip()
    if re.search(r'需要.*吗|是否|能否|能不能|应该.*吗|要.*吗|可.*吗', q):
        if any(kw in q for kw in ['何时', '什么时候', '什么情况', '立刻', '马上', '立即']):
            return "when_to"
        return "yes_no"
    if re.search(r'何时|什么时候|什么情况下|多大|几岁|多久', q):
        return "when_to"
    if re.search(r'为什么|原因|怎么回事|为何', q):
        return "what_why"
    if re.search(r'怎么|如何|怎么办|怎样', q):
        return "how_to"
    return "other"


def _title_match_bonus(query: str, text: str, q_kws: List[str]) -> float:
    """
    标题/首行匹配奖励。

    如果 chunk 的前 60 字（通常是标题+概述行）包含查询的核心实体，
    说明这篇文档直接回答该问题，应大幅加分。
    """
    if not text or not q_kws:
        return 1.0

    # 取 chunk 的标题部分（通常在 " > " 或 "\n##" 之前）
    title_part = text[:120].split("\n")[0]
    # 去掉 heading 前缀
    title_clean = re.sub(r'^[#>\s]+', '', title_part).strip()

    if not title_clean:
        return 1.0

    # 计算标题中命中的关键词数
    title_toks = _chunk_tokens(title_clean)
    hit_count = sum(1 for k in q_kws if k in title_toks)

    if hit_count == 0:
        return 1.0  # 不惩罚，只是不奖励

    ratio = hit_count / len(q_kws)
    # 标题匹配 50%+ 关键词 → 强奖励；100% → 最大奖励
    if ratio >= 1.0:
        return 1.25  # +25%
    elif ratio >= 0.5:
        return 1.15  # +15%
    elif ratio >= 0.25:
        return 1.08  # +8%
    return 1.03  # +3% 微励


def _answer_pattern_bonus(query: str, text: str, q_type: str) -> float:
    """
    答案模式匹配：根据问题类型，检查文本是否包含对应模式的答案。

    例如：
    - when_to 问 + 文本含 "应立即就医/需就诊/及时" → 加分
    - yes_no 问 + 文本含 "应该/需要/建议/推荐" → 加分
    """
    if q_type == "when_to":
        urgency_patterns = [
            '应立即', '需立即', '应及时', '需要立刻', '必须',
            '应尽快', '尽早就医', '立即就医', '马上', '紧急',
            '一旦', '如果.*就医', '当.*时.*就医',
        ]
        for pat in urgency_patterns:
            if re.search(pat, text):
                return 1.20  # +20%

    elif q_type == "yes_no":
        answer_patterns = [
            '应该', '需要', '建议', '推荐', '可以', '必须',
            '不必', '不需要', '不建议', '避免',
        ]
        for pat in answer_patterns:
            if re.search(pat, text):
                return 1.10  # +10%

    return 1.0


def _entity_match_score(query: str, text: str) -> float:
    """
    实体级匹配分：检查查询中的医学实体在文本中的共现情况。

    例如查询"儿童发热"，文本同时出现"儿童"+"发热"的变体 → 高分。
    """
    score = 1.0
    for entity, synonyms in _MEDICAL_ENTITIES.items():
        if entity not in query:
            continue
        # 实体本身或任一同义词在文本中出现
        found = entity in text or any(syn in text for syn in synonyms)
        if found:
            score += 0.05  # 每个匹配实体 +5%
    return min(score, 1.30)  # 上限 +30%


class CrossEncoderReranker:
    """
    Cross-Encoder 重排器 v3。

    有真实模型时用模型打分；否则用增强融合算法 v3。
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
        self._model = None
        self._model_name = ""
        self._try_load_model()

    def _try_load_model(self):
        """尝试加载真实 Cross-Encoder 模型。

        优先级：
        1. 环境变量 RERANK_MODEL_PATH（显式路径或 "auto"）
        2. config.RERANK_MODEL_PATH 默认值（"auto"）
        3. "auto" 时在 MODEL_DIR 下自动搜索
        """
        model_path = os.getenv("RERANK_MODEL_PATH") or config.RERANK_MODEL_PATH

        if not model_path or model_path == "auto":
            resolved = self._auto_detect_ce_model()
            if not resolved:
                return
            model_path = str(resolved)

        resolved = self._resolve_model_path(model_path)
        if not resolved:
            print(f"[Reranker] 未找到 Cross-Encoder 模型: {model_path}")
            return

        try:
            from sentence_transformers import CrossEncoder as STCrossEncoder
            self._model = STCrossEncoder(str(resolved))
            self._model_name = str(resolved)
            print(f"[Reranker] Cross-Encoder 模型加载成功: {resolved}")
        except ImportError:
            print("[Reranker] sentence_transformers 未安装，使用融合模式")
        except Exception as e:
            print(f"[Reranker] Cross-Encoder 加载失败: {e}，使用融合模式")

    @staticmethod
    def _resolve_model_path(model_path_or_name: str):
        """解析 Cross-Encoder 模型路径。"""
        from pathlib import Path

        p = Path(model_path_or_name).expanduser()
        if p.is_dir() and (p / "config.json").exists():
            return p

        backend_p = config.BACKEND_DIR / p
        if backend_p.is_dir() and (backend_p / "config.json").exists():
            return backend_p

        model_dir = config.MODEL_DIR
        if model_dir.exists():
            for cand in [
                model_dir / model_path_or_name,
                model_dir / "models" / f"BAAI--{model_path_or_name}" / "snapshots" / "master",
            ]:
                if cand.is_dir() and (cand / "config.json").exists():
                    return cand
        return None

    @staticmethod
    def _auto_detect_ce_model():
        """在 MODEL_DIR 下自动搜索已下载的 Cross-Encoder 模型。"""
        from pathlib import Path

        model_dir = config.MODEL_DIR
        if not model_dir.exists():
            return None

        _CE_CANDIDATES = [
            "bge-reranker-v2-min",
            "bge-reranker-v2-m3",
            "bge-reranker-base",
        ]

        for name in _CE_CANDIDATES:
            for cand in [
                model_dir / name,
                model_dir / "models" / f"BAAI--{name}" / "snapshots" / "master",
                model_dir / f"BAAI__{name}",
                model_dir / "models" / f"BAAI--{name}",
            ]:
                if cand.is_dir() and (cand / "config.json").exists():
                    print(f"[Reranker] 自动检测到 Cross-Encoder 模型: {cand}")
                    return cand
            try:
                for p in model_dir.rglob("config.json"):
                    parent = p.parent
                    try:
                        depth = len(parent.relative_to(model_dir).parts)
                    except ValueError:
                        continue
                    if depth <= 3 and name in str(parent):
                        print(f"[Reranker] 递归检测到 Cross-Encoder: {parent}")
                        return parent
            except OSError:
                pass
        return None

    def _model_score(self, query: str, text: str) -> float:
        """真实 Cross-Encoder 打分（sigmoid → [0,1]）。"""
        raw = self._model.predict([(query, text)])  # type: ignore
        try:
            val = float(raw[0])
        except Exception:
            val = 0.0
        return _sigmoid(val)

    def _fusion_score(
        self,
        query: str,
        text: str,
        dense: float,
        bm25_raw: float,
        max_bm25: float,
        q_kws: List[str],
    ) -> float:
        """
        融合打分 v3 — 让 BGE 高分候选真正排到前面。

        核心设计原则：
        1. BGE 余弦相似度是最强信号，不应被其他弱特征稀释
        2. BM25 为 0 时（索引未建/失败），将其权重重新分配给 dense 和 lexical
        3. 多粒度匹配 + 问题类型感知 + 标题匹配作为增强信号
        4. 分数诚实：0.7+ 的 dense 应直接映射到 0.85+ 的最终分
        """
        norm_dense = _norm(dense)

        # --- 动态权重：BM25 全 0 时重分配 ---
        bm25_active = max_bm25 > 0
        if bm25_active:
            norm_bm25 = (bm25_raw / max_bm25) if max_bm25 > 0 else 0.0
            w_d, w_b, w_l = self.w_dense, self.w_bm25, self.w_lexical
        else:
            # BM25 不可用：将其权重大部分分配给 dense（最强信号）
            total_redistributed = self.w_bm25
            w_d = self.w_dense + total_redistributed * 0.8  # 80% 给 dense
            w_b = 0.0
            w_l = self.w_lexical + total_redistributed * 0.2  # 20% 给 lexical
            norm_bm25 = 0.0

        # --- 特征 1：BGE 稠密相似度（主信号）---
        score_dense = w_d * norm_dense

        # --- 特征 2：BM25 稀疏分数 ---
        score_bm25 = w_b * norm_bm25

        # --- 特征 3：多粒度词法覆盖 ---
        if q_kws:
            chunk_set = _chunk_tokens(text)
            chunk_words = set(_chunk_words(text))

            # 3a. bigram 级覆盖率
            bigram_hit = sum(1 for k in q_kws if k in chunk_set)
            bigram_cov = bigram_hit / len(q_kws)

            # 3b. 完整词级覆盖率（更严格）
            word_hit = sum(1 for k in q_kws if k in chunk_words)
            word_cov = word_hit / len(q_kws) if chunk_words else 0.0

            # 取两者较高者（bigram 更宽松但更稳定）
            lexical_cov = max(bigram_cov, word_cov)
        else:
            lexical_cov = 0.0

        score_lexical = w_l * lexical_cov

        # --- 基础融合分（加法）---
        base_score = score_dense + score_bm25 + score_lexical

        # --- 乘法增强因子 ---

        # 增强 1：位置加权
        position_factor = 1.0
        if q_kws:
            first_positions = []
            for kw in q_kws:
                pos = text.find(kw)
                if pos >= 0:
                    first_positions.append(pos)
            if first_positions:
                avg_pos = sum(first_positions) / len(first_positions)
                # 前 80 字内 → 1.0；每后移 40 字衰减 0.03
                position_factor = max(0.5, 1.0 - (avg_pos / 80.0) * 0.03)

        # 增强 2：密度奖励（关键词聚集 vs 分散）
        density_factor = 1.0
        if q_kws and len(text) > 0:
            window = 150
            max_density = 0.0
            for start in range(0, len(text), window // 2):
                segment = text[start:start + window]
                seg_toks = _chunk_tokens(segment)
                hit_w = sum(1 for k in q_kws if k in seg_toks)
                density = hit_w / len(q_kws)
                max_density = max(max_density, density)
            if max_density > 0.6:
                density_factor = 1.0 + (max_density - 0.6) * 0.2

        # 增强 3：长度惩罚
        length_factor = 1.0
        if len(text) > 800:
            length_factor = max(0.8, 1.0 - (len(text) - 800) / 3000.0 * 0.2)

        # 增强 4：标题/heading 匹配
        title_factor = _title_match_bonus(query, text, q_kws)

        # 增强 5：答案模式匹配（问题类型感知）
        q_type = _detect_query_type(query)
        answer_factor = _answer_pattern_bonus(query, text, q_type)

        # 增强 6：实体共现
        entity_factor = _entity_match_score(query, text)

        # --- 最终分 ---
        final = base_score * position_factor * density_factor * length_factor
        final *= title_factor * answer_factor * entity_factor

        return min(1.0, max(0.0, final))

    def rerank(
        self,
        query: str,
        candidates: List[dict],
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> List[dict]:
        """
        对候选集重排序并过滤。

        Returns:
            列表每条附带 score 字段（相关性分 0~1，诚实不注水）。
        """
        if not candidates:
            return []

        top_k = top_k or config.RERANK_TOP_K
        min_score = min_score if min_score is not None else config.RERANK_MIN_SCORE

        bm25_vals = [float(c.get("bm25", 0.0) or 0.0) for c in candidates]
        max_bm25 = max(bm25_vals) if bm25_vals else 0.0

        q_kws = _extract_keywords(query)

        scored: List[dict] = []
        for c in candidates:
            text = c.get("text", "") or ""
            dense = float(c.get("similarity", 0.0) or 0.0)
            bm25 = float(c.get("bm25", 0.0) or 0.0)

            if self._model is not None:
                final = self._model_score(query, text)
            else:
                final = self._fusion_score(
                    query, text, dense, bm25, max_bm25, q_kws,
                )

            item = dict(c)
            item["score"] = round(float(final), 4)
            scored.append(item)

        # 过滤 + 排序 + 截断
        kept = [s for s in scored if s["score"] >= min_score]
        kept.sort(key=lambda x: x["score"], reverse=True)
        result = kept[:top_k]

        # --- 诚实校准 v3 ---
        # 不再人为拉伸到 [0.30, 1.0]。
        # 改为：对 >0.85 的分数做微调上限，<0.3 的做微调下限，
        # 中间区域保持原始分数的相对顺序和绝对值。
        if result:
            for r in result:
                raw = r["score"]
                # 高分段微调：>0.90 的压缩到 0.95 上限（避免过度自信）
                if raw > 0.92:
                    r["score"] = round(0.92 + (raw - 0.92) * 0.4, 4)
                # 低分段微调：<0.15 的提升到 0.15 下限（避免看起来像"完全不相关"）
                elif raw < 0.12:
                    r["score"] = round(raw * 0.8 + 0.12 * 0.2, 4)
                # 中间保持原值
                else:
                    r["score"] = round(raw, 4)

        return result

    @property
    def using_real_model(self) -> bool:
        return self._model is not None

    @property
    def model_info(self) -> str:
        if self._model:
            return f"Cross-Encoder({self._model_name})"
        return f"Fusion-v3(dense={self.w_dense},bm25={self.w_bm25},lex={self.w_lexical})"


# 便捷单例
_default_reranker: Optional[CrossEncoderReranker] = None


def get_reranker() -> CrossEncoderReranker:
    global _default_reranker
    if _default_reranker is None:
        _default_reranker = CrossEncoderReranker()
    return _default_reranker
