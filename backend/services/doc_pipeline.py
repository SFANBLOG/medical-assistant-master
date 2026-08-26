"""文档入库流水线：抽取文本 -> 父子块切分 -> 生成 bge 向量 -> BM25 统计 -> MySQL 落盘 -> Milvus/NumpyStore 入库。"""
import datetime
import json
import os
from collections import Counter

from extensions import get_vector_store, get_llm
from flask import current_app
from models.db import get_conn
from utils.file_utils import extract_text
from utils.text_utils import chunk_document_parent_child, tokenize


def _save_sub_chunk_vector(sub_chunk_id: int, doc_id: int, kb_id: int,
                           vector: list[float], cfg: dict) -> str:
    """把子块向量持久化到本地 JSON（Milvus 兜底或作为缓存），返回相对路径。"""
    vec_dir = os.path.join(cfg["VECTOR_DIR"], "sub_chunks")
    os.makedirs(vec_dir, exist_ok=True)
    rel = os.path.join("sub_chunks", f"{kb_id}_{doc_id}_{sub_chunk_id}.json")
    abs_path = os.path.join(cfg["VECTOR_DIR"], rel)
    with open(abs_path, "w", encoding="utf-8") as f:
        json.dump(vector, f, ensure_ascii=False)
    return rel


def _compute_bm25_terms(text: str) -> dict:
    """返回 {term: tf} 的词频映射。"""
    toks = tokenize(text)
    if not toks:
        return {}
    counter = Counter(toks)
    total = len(toks)
    # 存储归一化 tf 与原始 tf
    return {term: {"tf": count, "norm": round(count / total, 6)} for term, count in counter.items()}


def _update_bm25_stats(conn, kb_id: int, sub_chunks: list[dict]) -> None:
    """按知识库更新 BM25 词频/文档频率统计。"""
    from models.db import MysqlConn

    term_doc_freq: Counter = Counter()
    term_coll_freq: Counter = Counter()
    for sc in sub_chunks:
        terms = set(sc.get("bm25_terms", {}).keys())
        for term in terms:
            term_doc_freq[term] += 1
            term_coll_freq[term] += sc["bm25_terms"][term]["tf"]

    if not term_doc_freq:
        return
    for term, df in term_doc_freq.items():
        cf = term_coll_freq[term]
        if isinstance(conn, MysqlConn):
            conn.execute(
                "INSERT INTO bm25_terms (kb_id, term, df, cf) VALUES (?,?,?,?) "
                "ON DUPLICATE KEY UPDATE df=df+VALUES(df), cf=cf+VALUES(cf), updated_at=NOW()",
                (kb_id, term, df, cf),
            )
        else:
            conn.execute(
                "REPLACE INTO bm25_terms (kb_id, term, df, cf) VALUES (?,?,?,?)",
                (kb_id, term, df, cf),
            )


def reindex_missing(cfg) -> dict:
    """对所有 status != 'ready' 或没有向量的文档重新执行 process_document。

    用于修复「MySQL 里有文档记录但向量库为空」的故障。
    """
    conn = get_conn()
    rows = conn.execute(
        """SELECT d.id, d.kb_id, d.file_path, d.filename, d.visibility
           FROM documents d
           LEFT JOIN chunk_vectors v ON v.doc_id = d.id
           WHERE d.status != 'ready' OR v.id IS NULL"""
    ).fetchall()
    ok = fail = 0
    for r in rows:
        abs_path = os.path.join(cfg["UPLOAD_DIR"], r["file_path"])
        try:
            process_document(r["id"], r["kb_id"], abs_path, r["filename"], r["visibility"])
            ok += 1
        except Exception as e:  # noqa: BLE001
            conn.execute(
                "UPDATE documents SET status='failed', error=? WHERE id=?",
                (str(e)[:500], r["id"]),
            )
            conn.commit()
            fail += 1
    return {"total": len(rows), "success": ok, "failed": fail}


def process_document(doc_id: int, kb_id: int, file_path: str, filename: str,
                     visibility: str = "public") -> dict:
    """处理单个文档：父子块切分 -> MySQL 落盘 -> 生成 bge 向量 -> Milvus/NumpyStore 入库。"""
    cfg = current_app.config
    conn = get_conn()
    try:
        text = extract_text(file_path)
        if not text or not text.strip():
            conn.execute(
                "UPDATE documents SET status='ready', chunk_count=0 WHERE id=?",
                (doc_id,),
            )
            conn.commit()
            return dict(conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())

        # 1) 父子块切分
        parents, children = chunk_document_parent_child(
            text,
            parent_size=cfg.get("CHUNK_SIZE", 380) * 2,
            child_size=cfg.get("CHUNK_SIZE", 380),
            child_overlap=cfg.get("CHUNK_OVERLAP", 60),
        )
        if not children:
            conn.execute(
                "UPDATE documents SET status='ready', chunk_count=0 WHERE id=?",
                (doc_id,),
            )
            conn.commit()
            return dict(conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())

        # 2) 清理该文档旧块/向量（幂等重入）
        conn.execute("DELETE FROM sub_chunks WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM chunk_vectors WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
        conn.commit()

        # 3) 写入父块
        parent_db_ids: dict[str, int] = {}
        for pi, p in enumerate(parents):
            cur = conn.execute(
                """INSERT INTO chunks (doc_id, kb_id, parent_id, chunk_index, heading, text, token_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, kb_id, None, pi, p["heading"], p["text"], p["token_count"]),
            )
            parent_db_ids[p["id"]] = cur.lastrowid

        # 4) 写入子块并计算 BM25
        sub_db_ids: dict[str, int] = {}
        bm25_map: dict[int, dict] = {}
        for ci, c in enumerate(children):
            bm25_terms = _compute_bm25_terms(c["text"])
            parent_db_id = parent_db_ids.get(c["parent_id"])
            cur = conn.execute(
                """INSERT INTO sub_chunks (chunk_id, doc_id, kb_id, sub_index, text, bm25_terms, token_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (parent_db_id, doc_id, kb_id, ci, c["text"], json.dumps(bm25_terms, ensure_ascii=False),
                 c["token_count"]),
            )
            sub_db_ids[c["id"]] = cur.lastrowid
            bm25_map[cur.lastrowid] = bm25_terms
            c["db_id"] = cur.lastrowid
            c["bm25_terms"] = bm25_terms

        # 5) 生成 bge 向量并写入本地缓存
        llm = get_llm(cfg)
        child_texts = [c["text"] for c in children]
        vectors = llm.embed(child_texts)
        for c, vec in zip(children, vectors):
            rel_path = _save_sub_chunk_vector(c["db_id"], doc_id, kb_id, vec, cfg)
            conn.execute(
                "UPDATE sub_chunks SET vector_path=? WHERE id=?",
                (rel_path, c["db_id"]),
            )

        # 6) 更新 BM25 统计
        _update_bm25_stats(conn, kb_id, children)

        # 7) 写入向量库（Milvus / NumpyStore）：子块为检索单元，metadata 带 parent_id 便于召回后扩展上下文
        ids = [f"{doc_id}:{c['db_id']}" for c in children]
        metadatas = [
            {"doc_id": doc_id, "kb_id": kb_id, "chunk_index": idx,
             "filename": filename, "visibility": visibility,
             "heading": c.get("heading", ""), "parent_id": c.get("parent_id", "")}
            for idx, c in enumerate(children)
        ]
        store = get_vector_store(cfg)
        store.upsert(kb_id, ids, vectors, child_texts, metadatas)

        # 8) 记录向量元数据
        for c, sid in zip(children, ids):
            store_type = "milvus" if type(store).__name__ == "MilvusStore" else "numpy"
            conn.execute(
                """INSERT INTO chunk_vectors (sub_chunk_id, doc_id, kb_id, store_type, store_key)
                   VALUES (?, ?, ?, ?, ?)""",
                (c["db_id"], doc_id, kb_id, store_type, str(sid)),
            )

        # 9) 使旧缓存失效
        try:
            from services.cache import clear_prefix
            clear_prefix("rag:hits:")
        except Exception:  # noqa: BLE001
            pass

        conn.execute(
            "UPDATE documents SET status='ready', chunk_count=?, indexed_at=? WHERE id=?",
            (len(children), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), doc_id),
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
