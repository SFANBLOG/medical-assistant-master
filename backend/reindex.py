# -*- coding: utf-8 -*-
"""
知识库重建脚本：清空并重建「知识库 → 文档 → 向量」全链路。

解决的问题
----------
1. chunk 的 doc_id 与 documents 表主键错位：
   向量库里残留旧一轮 seed 的 doc_id，而 documents 表已被重建/改号，
   导致 retriever 用 doc_id 反查文件名时张冠李戴
   （例如问「糖尿病」却引用到《肥胖症.md》，且相似度很低）。

2. 知识库/文档被清空后 RAG 无数据可检索。

做法：以「磁盘上的 .md 文件」为准，重新注册文档、重新切分、重新向量化，
从而保证 chunk 的 doc_id 与 documents 表严格一致。

用法：
    python -m backend.reindex          # 重建（默认）
    python -m backend.reindex --force  # 即使已有文档也强制重建
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils.db import fetchone, execute  # noqa: E402
from backend.rag.vectorstore import get_vectorstore  # noqa: E402
from backend.rag.embedder import get_embedder  # noqa: E402


def rebuild(force: bool = False) -> None:
    doc_cnt = fetchone("SELECT COUNT(*) AS cnt FROM documents")["cnt"]
    kb_cnt = fetchone("SELECT COUNT(*) AS cnt FROM knowledge_bases")["cnt"]

    if doc_cnt and not force:
        print(f"[reindex] documents 已有 {doc_cnt} 条，跳过。"
              f"（如需强制重建：python -m backend.reindex --force）")
        return

    print("=" * 66)
    print("  知识库重建")
    print("=" * 66)
    print(f"  重建前: knowledge_bases={kb_cnt}, documents={doc_cnt}")

    # 1. 知识库缺失时先补齐（12 个疾病库 + 私有库）
    if kb_cnt == 0:
        print("[reindex] 知识库为空，先创建知识库...")
        from backend.seed import seed_knowledge_bases
        seed_knowledge_bases()
    else:
        print(f"[reindex] 知识库已存在 {kb_cnt} 个，保留。")

    # 2. 清空旧向量 + 旧文档记录（保证 doc_id 重新对齐）
    print("[reindex] 清空旧向量与文档记录...")
    vs = get_vectorstore()
    vs.clear()
    execute("DELETE FROM citations")
    execute("DELETE FROM documents")

    # 3. 以磁盘文件为准，重新切分 + 向量化
    print("[reindex] 按磁盘文件重新注册文档并向量化...")
    from backend.seed import seed_documents_and_vectors
    embedder = get_embedder()
    print(f"[reindex] embedder dim = {embedder.dim}")
    seed_documents_and_vectors()

    # 4. 失效的会话 kb_id 置空，避免指向已删除的知识库
    execute(
        "UPDATE conversations c "
        "LEFT JOIN knowledge_bases k ON c.kb_id = k.id "
        "SET c.kb_id = NULL "
        "WHERE c.kb_id IS NOT NULL AND k.id IS NULL"
    )

    new_doc = fetchone("SELECT COUNT(*) AS cnt FROM documents")["cnt"]
    print(f"[reindex] 重建完成: documents={new_doc}, 向量={vs.count}")

    # 5. 校验：chunk 的 doc_id 是否都能在 documents 表查到
    _verify()

    print("=" * 66)


def _verify() -> None:
    """校验向量库 chunk 的 doc_id 与 documents 表是否一一对齐。"""
    vs = get_vectorstore()
    chunks = vs.get_all_chunks()
    doc_ids = {r["id"] for r in []}  # placeholder
    try:
        from backend.utils.db import fetchall
        doc_ids = {r["id"] for r in fetchall("SELECT id FROM documents")}
    except Exception as e:  # noqa: BLE001
        print(f"[verify] 读取 documents 失败: {e}")
        return

    missing = {c["doc_id"] for c in chunks if c["doc_id"] not in doc_ids}
    if missing:
        print(f"[verify] 仍有 {len(missing)} 个 doc_id 对不上: {sorted(missing)[:10]}")
    else:
        print(f"[verify] 校验通过：{len(chunks)} 个 chunk 的 doc_id 全部对齐")


if __name__ == "__main__":
    rebuild(force="--force" in sys.argv)
