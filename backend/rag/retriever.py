"""
混合检索器：BM25 稀疏 + BGE 稠密向量 + Cross-Encoder 重排 + 查询扩展。

检索流水线：

    用户查询
        ↓
    0. 查询扩展（医学同义词 → 增强查询）
        ↓
    1. BM25 稀疏检索（召回 top30，jieba 分词）
       + BGE 稠密向量检索（召回 top30，真实语义嵌入）
        ↓
    2. 合并、去重得到候选集（约 40-50 条）
        ↓
    3. Cross-Encoder Reranker 重排序（真实模型 / 增强融合）
       → 过滤低相关文档，取 top-3~top-5
        ↓
    4. 分数校准 → 补元数据 → 返回

关键改进（v2）：
- BGE 真实语义嵌入替代 MD5 哈希向量（核心修复）
- jieba 分词替代 单字+bigram（BM25 召回质量提升）
- 查询扩展（医学同义词）提升召回率
- 增强融合算法（位置加权/密度奖励/长度惩罚）
- 分数校准到直觉百分比区间
"""
from typing import Optional

from backend import config
from backend.rag.embedder import get_embedder
from backend.rag.vectorstore import get_vectorstore
from backend.rag.bm25 import BM25Index
from backend.rag.reranker import get_reranker
from backend.rag.llm import _clean_answer_text
from backend.utils.db import fetchall


# ---- BM25 索引（懒加载单例，随向量库内容构建一次）----
_bm25_index: Optional[BM25Index] = None
_bm25_built_for_count: int = -1

# ---- 医学同义词表（查询扩展用）----
_MEDICAL_SYNONYMS: dict[str, list[str]] = {
    # === 发热/体温 ===
    "发热": ["发烧", "体温升高", "高热", "低热", "体温异常", "发热待查"],
    "发烧": ["发热", "体温升高", "高热"],
    "体温": ["温度", "体温度数", "热度", "℃"],
    "高热": ["高烧", "39度以上", "超高热"],
    "退烧": ["降温", "退热", "物理降温", "药物降温"],

    # === 人群 ===
    "儿童": ["小儿", "小孩", "幼儿", "婴幼儿", "孩童", "宝宝", "患儿"],
    "小孩": ["儿童", "小儿", "幼儿"],
    "婴儿": ["婴幼儿", "新生儿", "小宝宝"],
    "成人": ["成年人", "大人", "成人患者"],
    "老人": ["老年人", "高龄", "长者", "老年患者"],

    # === 动作/ urgency ===
    "立刻": ["马上", "立即", "赶紧", "迅速", "及时", "尽快"],
    "就医": ["看医生", "去医院", "就诊", "挂号", "求医", "急诊", "尽早就医"],
    "需要": ["应该", "必须", "要", "建议", "推荐"],
    "不用": ["不必", "不需要", "不建议", "避免", "无需"],

    # === 呼吸系统 ===
    "咳嗽": ["咳", "干咳", "咳喘", "咳嗽咳痰"],
    "肺炎": ["肺部感染", "肺感染", "大叶性肺炎", "支气管肺炎"],
    "感冒": ["上感", "上呼吸道感染", "流感", "普通感冒", "急性鼻炎"],
    "哮喘": ["支气管哮喘", "喘息", "气喘"],
    "腹泻": ["拉肚子", "腹泻", "便溏", "消化不良", "急性胃肠炎"],
    "呕吐": ["恶心呕吐", "反胃", "呕逆"],

    # === 症状 ===
    "疼痛": ["痛", "疼", "酸痛", "胀痛", "刺痛", "绞痛"],
    "头痛": ["头疼", "头晕头痛", "偏头痛"],
    "腹痛": ["肚子疼", "胃痛", "腹疼", "腹部疼痛"],
    "胸痛": ["胸闷", "胸口痛", "胸骨后疼痛"],
    "皮疹": ["红疹", "斑疹", "丘疹", "皮肤红点", "出疹子"],
    "惊厥": ["抽搐", "抽风", "惊风", "癫痫发作", "意识丧失"],
    "脱水": ["缺水", "体液不足", "口干尿少"],
    "休克": ["血压下降", "循环衰竭", "意识模糊", "四肢湿冷"],
    "昏迷": ["意识不清", "神志不清", "失去意识", "不醒"],

    # === 过敏/免疫 ===
    "过敏": ["变态反应", "过敏性", "敏感", "过敏反应", "荨麻疹"],
    "疫苗": ["疫苗接种", "预防针", "免疫接种"],

    # === 感染 ===
    "细菌": ["细菌感染", "革兰阳性菌", "革兰阴性菌"],
    "病毒": ["病毒感染", "呼吸道病毒", "肠道病毒"],
    "感染": ["发炎", "炎症反应", "传染"],

    # === 就医判断关键词 ===
    "严重": ["危急", "重症", "厉害", "剧烈", "加重", "恶化"],
    "危险": ["风险", "高危", "隐患", "并发症"],
    "症状": ["表现", "征象", "迹象", "不适", "主诉"],
    "原因": ["病因", "诱因", "起因", "病原"],
    "预防": ["防止", "避免", "防护", "注意事项", "护理"],
}


def _expand_query(query: str) -> str:
    """
    查询扩展 v2：在原始查询后追加医学同义词，提升 BM25 召回率。

    策略（v2 改进）：
    1. 按语义角色分类扩展（人群/症状/动作/urgency），每类最多 2 个
    2. 优先短词（BM25 对短词匹配更精确）
    3. 总共最多追加 6 个词（比 v1 的 4 个稍宽松）
    4. 避免添加查询中已存在的词
    """
    # 按角色分类收集候选同义词
    role_groups: dict[str, list[str]] = {
        "symptom": [],   # 症状类
        "population": [], # 人群类
        "action": [],    # 动作/就医类
        "urgency": [],   # 紧急程度类
        "other": [],
    }

    # 角色映射
    _ROLE_MAP: dict[str, str] = {
        "发热": "symptom", "发烧": "symptom", "体温": "symptom", "高热": "symptom",
        "咳嗽": "symptom", "肺炎": "symptom", "腹泻": "symptom", "疼痛": "symptom",
        "头痛": "symptom", "皮疹": "symptom", "惊厥": "symptom", "呕吐": "symptom",
        "过敏": "symptom", "感染": "symptom", "休克": "symptom", "脱水": "symptom",
        "儿童": "population", "小儿": "population", "婴儿": "population",
        "成人": "population", "老人": "population",
        "就医": "action", "就诊": "action", "治疗": "action", "预防": "action",
        "立刻": "urgency", "马上": "urgency", "及时": "urgency", "需要": "urgency",
        "严重": "urgency", "危险": "urgency",
    }

    added: list[str] = []
    for term, synonyms in _MEDICAL_SYNONYMS.items():
        if term not in query:
            continue
        role = _ROLE_MAP.get(term, "other")
        for syn in synonyms:
            if syn not in query and syn not in added:
                role_groups[role].append(syn)

    # 每个角色组取前 2 个，总共最多 6 个
    for role in ["symptom", "population", "action", "urgency", "other"]:
        for syn in role_groups[role][:2]:
            added.append(syn)
            if len(added) >= 6:
                break
        if len(added) >= 6:
            break

    if added:
        expanded = query + " " + " ".join(added)
        return expanded
    return query


def _ensure_bm25() -> Optional[BM25Index]:
    """按当前向量库内容构建（或复用）BM25 索引。"""
    global _bm25_index, _bm25_built_for_count
    try:
        vs = get_vectorstore()
        count = vs.count
        if _bm25_index is not None and _bm25_built_for_count == count:
            return _bm25_index
        chunks = vs.get_all_chunks()
        if not chunks:
            return None
        idx = BM25Index()
        idx.build(chunks)
        _bm25_index = idx
        _bm25_built_for_count = count
        print(f"[BM25] 索引构建完成，共 {idx.doc_count()} 个 chunk")
        return _bm25_index
    except Exception as e:  # noqa: BLE001
        print(f"[BM25] 索引构建失败（稀疏检索降级关闭）: {e}")
        return None


def retrieve(
    query: str,
    role: str,
    user_id: int,
    kb_id: Optional[int] = None,
    top_k: int = config.RERANK_TOP_K,
    min_similarity: float = config.DENSE_MIN_SIMILARITY,
) -> list[dict]:
    """
    混合检索：返回喂给 LLM 的最相关文档片段。

    Args:
        query: 用户提问
        role: 用户角色（patient/doctor/nurse/public/admin）
        user_id: 用户 ID
        kb_id: 指定知识库 ID；None 走角色默认；0 通用知识库（兜底）
        top_k: 最终保留条数（默认 RERANK_TOP_K）
        min_similarity: 稠密分支相似度下限（仅过滤纯噪声）

    Returns:
        [{"doc_id","chunk_index","text","similarity","filename","kb_name","kb_id"}]
        similarity 为重排后的融合相关性分（0~1，越高越相关）。
    """
    embedder = get_embedder()
    vs = get_vectorstore()

    # 1. 确定可见知识库列表
    kb_ids = _get_visible_kb_ids(role, user_id, kb_id)
    if not kb_ids:
        return []

    # ---- 阶段1：双分支召回 ----
    # 1a. 稠密向量检索（召回 top DENSE_TOP_K）
    query_vec = embedder.embed(query)
    dense_hits = vs.search(
        query_vec,
        kb_ids,
        top_k=config.DENSE_TOP_K,
        min_similarity=min_similarity,
    )

    # 1b. BM25 稀疏检索（用扩展查询召回 top BM25_TOP_K）
    bm25_hits: list[dict] = []
    bm25 = _ensure_bm25()
    if bm25 is not None:
        expanded_query = _expand_query(query)
        bm25_hits = bm25.search(expanded_query, kb_ids, top_k=config.BM25_TOP_K)

    # ---- 阶段2：合并、去重得到候选集 ----
    candidates: dict[tuple, dict] = {}
    for h in dense_hits:
        key = (h.get("doc_id"), h.get("chunk_index"))
        candidates[key] = {
            "id": h.get("id"),
            "kb_id": h.get("kb_id"),
            "doc_id": h.get("doc_id"),
            "chunk_index": h.get("chunk_index"),
            "text": h.get("text", ""),
            "similarity": h.get("similarity", 0.0),
            "bm25": 0.0,
        }
    for h in bm25_hits:
        key = (h.get("doc_id"), h.get("chunk_index"))
        if key in candidates:
            # 已存在：补上 BM25 分数，稠密相似度取较大者
            candidates[key]["bm25"] = h.get("bm25", 0.0)
            if h.get("similarity", 0.0) > candidates[key]["similarity"]:
                candidates[key]["similarity"] = h.get("similarity", 0.0)
        else:
            candidates[key] = {
                "id": h.get("id"),
                "kb_id": h.get("kb_id"),
                "doc_id": h.get("doc_id"),
                "chunk_index": h.get("chunk_index"),
                "text": h.get("text", ""),
                "similarity": h.get("similarity", 0.0),
                "bm25": h.get("bm25", 0.0),
            }

    if not candidates:
        return []

    # ---- 阶段3：Cross-Encoder 重排，过滤低相关，取 top-N ----
    reranker = get_reranker()
    reranked = reranker.rerank(
        query,
        list(candidates.values()),
        top_k=top_k,
        min_score=config.RERANK_MIN_SCORE,
    )
    if not reranked:
        return []

    # ---- 阶段4：补文档元数据 ----
    doc_ids = list({h["doc_id"] for h in reranked})
    docs = _get_doc_metadata(doc_ids)

    results = []
    for h in reranked:
        doc = docs.get(h["doc_id"], {})
        if not doc:
            # 文档未通过复核或处理未完成：跳过，不进入上下文
            continue
        results.append(
            {
                "doc_id": h["doc_id"],
                "chunk_index": h.get("chunk_index", 0),
                "text": h["text"],
                "similarity": round(h.get("score", h.get("similarity", 0.0)), 4),
                "filename": doc.get("filename", ""),
                "kb_name": doc.get("kb_name", ""),
                "kb_id": h.get("kb_id", doc.get("kb_id")),
            }
        )
    return results


def _get_visible_kb_ids(role: str, user_id: int, kb_id: Optional[int] = None) -> list[int]:
    """根据角色和权限，返回可见的知识库 ID 列表。

    kb_id 语义：
      - None       : 按角色默认可见范围
      - 0          : 通用知识库（兜底：返回当前角色可访问的全部知识库 ID 列表）
      - > 0        : 仅这一个知识库
    """
    # 通用知识库：按角色返回所有可访问的 KB（不筛选）
    if kb_id is not None and kb_id == 0:
        rows = fetchall("SELECT id FROM knowledge_bases WHERE visibility = 'public'")
        kb_ids = [r["id"] for r in rows]
        if role in ("doctor", "admin"):
            if role == "admin":
                private_rows = fetchall(
                    "SELECT id FROM knowledge_bases WHERE visibility = 'private'"
                )
            else:
                private_rows = fetchall(
                    "SELECT id FROM knowledge_bases WHERE visibility = 'private' "
                    "AND (owner_id IS NULL OR owner_id = %s)",
                    (user_id,),
                )
            kb_ids.extend(r["id"] for r in private_rows)
        # 去重保持顺序
        return list(dict.fromkeys(kb_ids))

    # ---- 正常分支：按 kb_id 取公开库 ----
    if kb_id:
        public_rows = fetchall(
            "SELECT id FROM knowledge_bases WHERE visibility = 'public' AND id = %s",
            (kb_id,),
        )
    else:
        public_rows = fetchall(
            "SELECT id FROM knowledge_bases WHERE visibility = 'public'"
        )
    kb_ids = [r["id"] for r in public_rows]

    # 医生和管理员可以查看私有知识库
    if role in ("doctor", "admin"):
        if kb_id:
            private_rows = fetchall(
                "SELECT id FROM knowledge_bases WHERE visibility = 'private' AND id = %s "
                "AND (owner_id IS NULL OR owner_id = %s OR %s = 'admin')",
                (kb_id, user_id, role),
            )
        elif role == "admin":
            private_rows = fetchall(
                "SELECT id FROM knowledge_bases WHERE visibility = 'private'"
            )
        else:
            private_rows = fetchall(
                "SELECT id FROM knowledge_bases WHERE visibility = 'private' "
                "AND (owner_id IS NULL OR owner_id = %s)",
                (user_id,),
            )
        kb_ids.extend(r["id"] for r in private_rows)

    return kb_ids


def _get_doc_metadata(doc_ids: list[int]) -> dict:
    """批量获取文档元数据。"""
    if not doc_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(doc_ids))
    # 仅返回「已复核通过且向量化完成」的文档：未复核(pending)/驳回(rejected)/处理中
    # 的文档不参与检索，避免未经人工确认的内容影响 AI 回答。
    rows = fetchall(
        f"""
        SELECT d.id, d.filename, d.kb_id, k.name AS kb_name
        FROM documents d
        JOIN knowledge_bases k ON d.kb_id = k.id
        WHERE d.id IN ({placeholders}) AND d.review_status = 'approved' AND d.status = 'ready'
        """,
        tuple(doc_ids),
    )
    return {r["id"]: r for r in rows}


def build_context(hits: list[dict], max_chars: int = 4000) -> str:
    """将检索结果构建为 LLM 上下文文本。"""
    if not hits:
        return ""
    parts = []
    total = 0
    for i, h in enumerate(hits, 1):
        text = _clean_answer_text(h["text"]).strip()
        source = h.get("filename", f"文档{h['doc_id']}")
        chunk = f"[{i}] 来源：{source}\n{text}\n"
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts)
