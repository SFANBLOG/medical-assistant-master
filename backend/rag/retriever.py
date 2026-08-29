"""
混合检索器：BM25 稀疏 + 稠密向量 + Cross-Encoder 重排。

检索流水线（与需求文档一致）：

    原始文档库
        ↓
    1. BM25 稀疏检索（召回 top30） + Embedding 稠密向量检索（召回 top30）
        ↓
    2. 合并、去重得到候选集（约 40-50 条）
        ↓
    3. Cross-Encoder Reranker 重排序，过滤低相关文档，取 top-3~top-5
        ↓
    4. 将 top-N 文档作为上下文喂给 LLM 生成答案

流程：query → embed → [向量检索 | BM25 检索] → 合并去重 → 重排过滤 → 补元数据
"""
from typing import Optional

from backend import config
from backend.rag.embedder import get_embedder
from backend.rag.vectorstore import get_vectorstore
from backend.rag.bm25 import BM25Index
from backend.rag.reranker import get_reranker
from backend.utils.db import fetchall


# ---- BM25 索引（懒加载单例，随向量库内容构建一次）----
_bm25_index: Optional[BM25Index] = None
_bm25_built_for_count: int = -1


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


def rebuild_bm25() -> None:
    """向量库内容变化后强制重建 BM25 索引（如重新索引文档后调用）。"""
    global _bm25_index, _bm25_built_for_count
    _bm25_index = None
    _bm25_built_for_count = -1


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

    # 1b. BM25 稀疏检索（召回 top BM25_TOP_K）
    bm25_hits: list[dict] = []
    bm25 = _ensure_bm25()
    if bm25 is not None:
        bm25_hits = bm25.search(query, kb_ids, top_k=config.BM25_TOP_K)

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
        text = h["text"].strip()
        source = h.get("filename", f"文档{h['doc_id']}")
        chunk = f"[{i}] 来源：{source}\n{text}\n"
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts)
