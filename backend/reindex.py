"""重建全部文档的向量索引（在更换向量模型 / 切分参数 / 向量库后执行）。

用途：升级到 bge-medical-zh 语义向量或切换到 Milvus 后，已有文档的向量仍是旧的
哈希向量，需要重新向量化入库，否则相似度会失真。

用法：
    .venv/bin/python reindex.py                 # 重建全部文档
    .venv/bin/python reindex.py --kb-id 1       # 只重建某个知识库
    .venv/bin/python reindex.py --doc-id 12     # 只重建某个文档
"""
import argparse
import logging
import os
import sys
import traceback

from flask import current_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reindex")


def _reindex_one(doc: dict, cfg) -> None:
    from extensions import get_vector_store
    from models.db import get_conn
    from utils.file_utils import extract_text
    from utils.text_utils import chunk_text

    doc_id = doc["id"]
    kb_id = doc["kb_id"]
    file_path = os.path.join(cfg["UPLOAD_DIR"], doc["file_path"] or "")

    conn = get_conn()
    if not os.path.exists(file_path):
        logger.warning(f"[doc {doc_id}] 文件不存在，跳过: {file_path}")
        conn.execute("UPDATE documents SET status='failed', error=? WHERE id=?",
                     ("文件缺失，无法重建索引", doc_id))
        conn.commit()
        return False

    try:
        text = extract_text(file_path)
        if not text or not text.strip():
            conn.execute("UPDATE documents SET status='ready', chunk_count=0 WHERE id=?", (doc_id,))
            conn.commit()
            logger.info(f"[doc {doc_id}] 空文档，无切片")
            return True

        chunks = chunk_text(text, cfg["CHUNK_SIZE"], cfg["CHUNK_OVERLAP"])
        from extensions import get_llm
        llm = get_llm(cfg)
        vectors = llm.embed(chunks)

        store = get_vector_store(cfg)
        # 先删除旧切片，再写入新切片（避免切分参数变化后残留旧 id）
        store.delete_doc(kb_id, doc_id)
        ids = [f"{doc_id}:{i}" for i in range(len(chunks))]
        metadatas = [
            {"doc_id": doc_id, "kb_id": kb_id, "chunk_index": i,
             "filename": doc["filename"], "visibility": doc["visibility"]}
            for i in range(len(chunks))
        ]
        store.upsert(kb_id, ids, vectors, chunks, metadatas)

        conn.execute(
            "UPDATE documents SET status='ready', chunk_count=?, error=NULL WHERE id=?",
            (len(chunks), doc_id),
        )
        conn.commit()
        logger.info(f"[doc {doc_id}] 重建完成：{doc['filename']} ({len(chunks)} 切片)")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"[doc {doc_id}] 重建失败: {e}\n{traceback.format_exc()}")
        conn.execute("UPDATE documents SET status='failed', error=? WHERE id=?",
                     (str(e)[:500], doc_id))
        conn.commit()
        return False


def main() -> None:
    from app import app

    parser = argparse.ArgumentParser(description="重建文档向量索引")
    parser.add_argument("--kb-id", type=int, default=None, help="只重建指定知识库")
    parser.add_argument("--doc-id", type=int, default=None, help="只重建指定文档")
    args = parser.parse_args()

    with app.app_context():
        cfg = current_app.config
        from models.db import get_conn

        conn = get_conn()
        sql = "SELECT * FROM documents"
        params: list = []
        if args.kb_id:
            sql += " WHERE kb_id = ?"
            params.append(args.kb_id)
        if args.doc_id:
            sql = "SELECT * FROM documents WHERE id = ?"
            params = [args.doc_id]
        docs = conn.execute(sql, params).fetchall()
        logger.info(f"待重建文档数：{len(docs)}")

        ok = fail = 0
        for doc in docs:
            if _reindex_one(dict(doc), cfg):
                ok += 1
            else:
                fail += 1
        logger.info(f"重建完成：成功 {ok}，失败 {fail}")


if __name__ == "__main__":
    sys.exit(main())
