# -*- coding: utf-8 -*-
"""
增量修复脚本：仅对「妇儿疾病」知识库（kb_id=12）重新做
「切块 → 嵌入 → 写入 Milvus」。
背景：documents 表已注册 20 篇（id 222~241，status=ready/approved），
但向量从未写入 Milvus（BM25 221 = 241 - 20，恰缺这批），导致检索不到。

用法（在 backend 容器内）：
    python /app/scripts/index_kb12.py
"""
import sys

sys.path.insert(0, "/app")

from pathlib import Path

from backend import config
from backend.rag.chunker import chunk_document
from backend.rag.embedder import get_embedder
from backend.rag.vectorstore import get_vectorstore, VectorRecord
from backend.utils.db import execute, fetchone
from backend.utils.file_parser import is_allowed, parse_file

KB_NAME = "妇儿疾病"
ph = "%s" if config.DB_TYPE == "mysql" else "?"


def main() -> None:
    kb_row = fetchone(f"SELECT id, name FROM knowledge_bases WHERE name = {ph}", (KB_NAME,))
    if not kb_row:
        print(f"[index] 知识库不存在: {KB_NAME}")
        return
    kb_id = kb_row["id"]
    print(f"[index] 知识库: {KB_NAME} (id={kb_id})")

    embedder = get_embedder()
    vs = get_vectorstore()
    uploads_dir = Path(config.UPLOAD_DIR)

    total_docs = 0
    total_chunks = 0
    for vis_folder in ("公开", "私有"):
        folder = uploads_dir / KB_NAME / vis_folder
        if not folder.exists():
            print(f"[index] 目录不存在: {folder}")
            continue
        for doc_file in sorted(
            p for p in folder.iterdir() if p.is_file() and is_allowed(p.name)
        ):
            rel_path = f"{KB_NAME}/{vis_folder}/{doc_file.name}"
            doc_row = fetchone(
                f"SELECT id, chunk_count FROM documents WHERE file_path = {ph}",
                (rel_path,),
            )
            if not doc_row:
                print(f"[skip] documents 无记录: {rel_path}")
                continue
            doc_id = doc_row["id"]

            try:
                file_text = parse_file(str(doc_file))
                chunks = chunk_document(file_text)
                if not chunks:
                    print(f"[skip] 无有效 chunk: {rel_path}")
                    continue

                embeddings = embedder.embed_batch([c.text for c in chunks])
                records = [
                    VectorRecord(
                        id=f"doc{doc_id}_chunk{c.index}",
                        kb_id=kb_id,
                        doc_id=doc_id,
                        chunk_index=c.index,
                        text=c.text,
                        embedding=e.tolist(),
                    )
                    for c, e in zip(chunks, embeddings)
                ]
                vs.insert_batch(records, flush=False)
                total_docs += 1
                total_chunks += len(chunks)
                print(f"[ok]   {rel_path}  doc_id={doc_id}  chunks={len(chunks)}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[ERROR] {rel_path}: {e}", flush=True)

    try:
        vs.flush()
        print("[index] flush 完成")
    except Exception as e:  # noqa: BLE001
        print(f"[index] flush 失败: {e}")

    print(f"[index] 完成: {total_docs} 篇 / {total_chunks} chunks 已写入 kb_id={kb_id}")


if __name__ == "__main__":
    main()
