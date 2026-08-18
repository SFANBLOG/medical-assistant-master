"""文档入库流水线：抽取文本 -> 切分 -> 向量化 -> 写入 Chroma。"""
from flask import current_app

from extensions import get_vector_store, get_llm
from models.db import get_conn
from utils.file_utils import extract_text
from utils.text_utils import chunk_text


def process_document(doc_id: int, kb_id: int, file_path: str, filename: str,
                     visibility: str = "public") -> dict:
    """处理单个文档，返回更新后的文档行。失败时置 status='failed' 并记录错误。"""
    cfg = current_app.config
    conn = get_conn()
    try:
        text = extract_text(file_path)
        if not text or not text.strip():
            # 空文档：无切片可入库，直接标记 ready
            conn.execute(
                "UPDATE documents SET status='ready', chunk_count=0 WHERE id=?",
                (doc_id,),
            )
            conn.commit()
            return dict(conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())
        chunks = chunk_text(text, cfg["CHUNK_SIZE"], cfg["CHUNK_OVERLAP"])
        llm = get_llm(cfg)
        vectors = llm.embed(chunks)

        ids = [f"{doc_id}:{i}" for i in range(len(chunks))]
        metadatas = [
            {"doc_id": doc_id, "kb_id": kb_id, "chunk_index": i,
             "filename": filename, "visibility": visibility}
            for i in range(len(chunks))
        ]
        store = get_vector_store(cfg)
        store.upsert(kb_id, ids, vectors, chunks, metadatas)

        conn.execute(
            "UPDATE documents SET status='ready', chunk_count=? WHERE id=?",
            (len(chunks), doc_id),
        )
        conn.commit()
    except Exception as e:  # noqa: BLE001
        conn.execute(
            "UPDATE documents SET status='failed', error=? WHERE id=?",
            (str(e)[:500], doc_id),
        )
        conn.commit()
        raise
    return dict(conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())
