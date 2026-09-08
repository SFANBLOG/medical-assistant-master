"""
一键重建向量索引：用 BGE 模型重新嵌入全部已审核文档。

用法：
    python scripts/reindex_vectors.py          # 全量重建
    python scripts/reindex_vectors.py --kb-id 3 # 只重建指定知识库

执行前会自动：
  1. 清除 numpy_store.pkl 中的旧向量（HashEmbedder 生成的 MD5 哈希向量）
  2. 从 DB 读取所有 review_status='approved' 且 status='ready' 的文档
  3. 用 BGE 模型重新切分 + 嵌入
  4. 写入新的 numpy_store.pkl
  5. 输出统计信息（文档数 / chunk 数 / 耗时）

注意：
  - 需要 sentence_transformers + torch 已安装
  - 需要 BGE 模型文件在 backend/data/models/ 下可被自动发现
  - Milvus 模式下也会重建 NumpyStore 兜底缓存（Milvus 侧需单独处理）
"""
import argparse
import os
import sys
import time

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DB_TYPE", "mysql")
os.environ.setdefault("MILVUS_ENABLE", "0")  # 重建时强制用 NumpyStore


def main():
    parser = argparse.ArgumentParser(description="用 BGE 重建全量向量索引")
    parser.add_argument("--kb-id", type=int, default=None, help="只重建指定知识库（默认全部）")
    args = parser.parse_args()

    from backend import config
    from backend.utils.db import fetchall, _placeholder
    from backend.rag.chunker import chunk_document
    from backend.rag.embedder import get_embedder
    from backend.rag.vectorstore import get_vectorstore, VectorRecord

    print("=" * 60)
    print("  向量索引重建工具（BGE 重嵌入）")
    print("=" * 60)

    # ---- 1. 验证 Embedder 是 BGE ----
    t0 = time.time()
    embedder = get_embedder()
    embedder_type = type(embedder).__name__
    print(f"\n[1/5] Embedder: {embedder_type} (dim={embedder.dim})")
    if embedder_type == "HashEmbedder":
        print("  错误：BGE 模型未加载！请检查 OPENAI_EMBED_MODEL 配置和模型文件。")
        print("  当前 HashEmbedder 生成的向量无语义，重建无意义。")
        sys.exit(1)
    print("  BGE 模型已加载")

    # ---- 2. 读取待重建文档 ----
    vs = get_vectorstore()
    kb_filter = ""
    params: list = []
    if args.kb_id:
        kb_filter = "AND d.kb_id = %s"
        params.append(args.kb_id)

    rows = fetchall(
        f"""
        SELECT d.id AS doc_id, d.kb_id, d.filename, d.file_path, d.file_type,
               k.name AS kb_name
        FROM documents d
        JOIN knowledge_bases k ON d.kb_id = k.id
        WHERE d.review_status = 'approved' AND d.status = 'ready'
              {kb_filter}
        ORDER BY d.kb_id, d.id
        """,
        tuple(params) if params else (),
    )
    print(f"\n[2/5] 找到 {len(rows)} 个待重建文档")

    if not rows:
        print("  无需重建的文档，退出。")
        return

    # ---- 3. 清除旧向量 ----
    vs.clear()
    print(f"[3/5] 已清除旧向量缓存")

    # ---- 4. 逐文档切分 + 嵌入 ----
    total_chunks = 0
    total_docs = 0
    errors = 0
    batch: list[VectorRecord] = []
    BATCH_SIZE = 50  # 每 50 条 chunk 写入一次

    for i, doc in enumerate(rows):
        file_path = doc["file_path"]
        full_path = config.UPLOAD_DIR / file_path

        if not full_path.exists():
            errors += 1
            print(f"  [{i+1}/{len(rows)}] 文件不存在，跳过: {file_path}")
            continue

        try:
            text = full_path.read_text(encoding="utf-8", errors="ignore")
            if not text.strip():
                errors += 1
                continue

            chunks = chunk_document(text)
            if not chunks:
                errors += 1
                continue

            chunk_texts = [c.text for c in chunks]
            embeddings = embedder.embed_batch(chunk_texts)

            for chunk, emb in zip(chunks, embeddings):
                batch.append(VectorRecord(
                    id=f"doc{doc['doc_id']}_chunk{chunk.index}",
                    kb_id=doc["kb_id"],
                    doc_id=doc["doc_id"],
                    chunk_index=chunk.index,
                    text=chunk.text,
                    embedding=emb.tolist(),
                ))
                total_chunks += 1

            total_docs += 1

            # 批量写入
            if len(batch) >= BATCH_SIZE:
                vs.insert_batch(batch)
                batch = []

            if (i + 1) % 20 == 0 or i == len(rows) - 1:
                print(f"  [{i+1}/{len(rows)}] {doc['filename']} "
                      f"({len(chunks)} chunks, 累计 {total_chunks})")

        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{len(rows)}] 处理失败: {doc['filename']} — {e}")

    # 写入剩余
    if batch:
        vs.insert_batch(batch)

    elapsed = time.time() - t0

    # ---- 5. 统计 ----
    print(f"\n[5/5] 重建完成")
    print(f"  文档数:   {total_docs}")
    print(f"  Chunk 数: {total_chunks}")
    print(f"  错误/跳过: {errors}")
    print(f"  向量总数: {vs.count}")
    print(f"  耗时:     {elapsed:.1f}s")
    if total_chunks > 0:
        print(f"  吞吐:     {total_chunks / elapsed:.1f} chunks/s")
    print(f"\n  Embedder: {embedder_type}")
    print(f"  存储:     NumpyStore ({config.DATA_DIR / 'numpy_store.pkl'})")


if __name__ == "__main__":
    main()
