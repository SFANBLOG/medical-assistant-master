"""文档入库流水线：抽取文本 -> 标题感知切分 -> 向量化 -> 写入向量库（Milvus / NumpyStore 兜底）。"""
import datetime

from extensions import get_vector_store, get_llm
from flask import current_app
from models.db import get_conn
from utils.file_utils import extract_text
from utils.text_utils import chunk_document


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
        # 标题感知切分：每块携带所属小节，去除近重复块
        chunks = chunk_document(text, cfg["CHUNK_SIZE"], cfg["CHUNK_OVERLAP"])
        llm = get_llm(cfg)
        vectors = llm.embed([c["text"] for c in chunks])

        ids = [f"{doc_id}:{i}" for i in range(len(chunks))]
        metadatas = [
            {"doc_id": doc_id, "kb_id": kb_id, "chunk_index": i,
             "filename": filename, "visibility": visibility,
             "heading": c.get("heading", "")}
            for i, c in enumerate(chunks)
        ]
        texts = [c["text"] for c in chunks]
        store = get_vector_store(cfg)
        store.upsert(kb_id, ids, vectors, texts, metadatas)

        # 文档索引变更后，使旧的检索结果缓存失效，避免返回过期上下文
        try:
            from services.cache import clear_prefix
            clear_prefix("rag:hits:")
        except Exception:  # noqa: BLE001
            pass

        conn.execute(
            "UPDATE documents SET status='ready', chunk_count=?, indexed_at=? WHERE id=?",
            (len(chunks), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), doc_id),
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
