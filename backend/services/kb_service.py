"""知识库与文档服务：所有权 / 角色权限校验。

角色权限：
- 医生/管理员：可创建知识库、管理公开知识库；
- 患者/护士/群众：只能浏览公开知识库（用于咨询），不可管理知识库。
"""
import os
import uuid

from models.db import get_conn
from utils.errors import ApiError


def can_manage_public(user: dict) -> bool:
    return user["role"] in ("doctor", "admin")


def can_create_kb(user: dict) -> bool:
    return user["role"] in ("doctor", "admin")


def can_view_kb(user: dict, kb: dict) -> bool:
    return user["role"] == "admin" or kb["visibility"] == "public" or kb["owner_id"] == user["id"]


def can_delete_kb(user: dict, kb: dict) -> bool:
    return user["role"] == "admin" or kb["owner_id"] == user["id"] or (
        can_manage_public(user) and kb["visibility"] == "public"
    )


def list_kbs(user: dict) -> list[dict]:
    conn = get_conn()
    if user["role"] == "admin":
        where, params = "1=1", []
    else:
        where, params = "(k.visibility = 'public' OR k.owner_id = ?)", [user["id"]]
    rows = conn.execute(
        f"""SELECT k.id, k.name, k.description, k.visibility, k.owner_id, k.created_at,
                  u.display_name AS owner_name,
                  (SELECT COUNT(*) FROM documents d WHERE d.kb_id = k.id) AS doc_count,
                  (SELECT COALESCE(SUM(d.chunk_count),0) FROM documents d WHERE d.kb_id = k.id) AS chunk_count
           FROM knowledge_bases k
           LEFT JOIN users u ON u.id = k.owner_id
           WHERE {where}
           ORDER BY k.created_at DESC""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def create_kb(user: dict, name: str, description: str = "", visibility: str = "private") -> dict:
    if not can_create_kb(user):
        raise ApiError("当前身份无权创建知识库", 403)
    if visibility not in ("private", "public"):
        raise ApiError("无效的可见性", 400)
    if visibility == "public" and not can_manage_public(user):
        raise ApiError("只有医生可将知识库设为公开", 403)
    name = name.strip()
    if not name:
        raise ApiError("知识库名称不能为空", 400)
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO knowledge_bases (owner_id, name, description, visibility) VALUES (?,?,?,?)",
        (user["id"], name, description, visibility),
    )
    conn.commit()
    return get_kb(user, cur.lastrowid)


def get_kb(user: dict, kb_id: int) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
    if not row:
        raise ApiError("知识库不存在", 404)
    kb = dict(row)
    if not can_view_kb(user, kb):
        raise ApiError("无权访问该知识库", 403)
    kb["doc_count"] = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE kb_id = ?", (kb_id,)
    ).fetchone()[0]
    return kb


def delete_kb(user: dict, kb_id: int) -> None:
    kb = get_kb(user, kb_id)
    if not can_delete_kb(user, kb):
        raise ApiError("无权删除该知识库", 403)
    # 删除 Chroma 集合
    from extensions import get_vector_store
    from flask import current_app

    store = get_vector_store(current_app.config)
    try:
        store.delete_collection(kb_id)
    except Exception:  # noqa: BLE001 集合可能不存在
        pass
    conn = get_conn()
    conn.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))
    conn.commit()


def list_documents(user: dict, kb_id: int) -> list[dict]:
    get_kb(user, kb_id)  # 权限校验
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM documents WHERE kb_id = ? ORDER BY created_at DESC", (kb_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _can_write_kb(user: dict, kb: dict) -> bool:
    # 仅医生/管理员可向知识库写入（患者/护士/群众不可管理知识库）
    return user["role"] in ("doctor", "admin")


def add_document(user: dict, kb_id: int, upload_file) -> dict:
    from flask import current_app

    cfg = current_app.config
    kb = get_kb(user, kb_id)
    if not _can_write_kb(user, kb):
        raise ApiError("无权向该知识库上传文档", 403)

    filename = upload_file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in cfg["ALLOWED_EXTENSIONS"]:
        raise ApiError(f"不支持的文件类型：仅支持 {', '.join(sorted(cfg['ALLOWED_EXTENSIONS']))}", 400)

    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO documents (kb_id, filename, file_path, file_type, status) VALUES (?,?,?,?,'processing')",
        (kb_id, filename, "", ext.lstrip(".")),
    )
    doc_id = cur.lastrowid
    conn.commit()

    # 落盘：UPLOAD_DIR/<知识库名>/<uuid>_<filename>，一个知识库对应一个文件夹
    from utils.file_utils import safe_folder_name

    kb_dir = os.path.join(cfg["UPLOAD_DIR"], safe_folder_name(kb["name"], str(kb_id)))
    os.makedirs(kb_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:12]}_{os.path.basename(filename)}"
    rel_path = os.path.join(safe_folder_name(kb["name"], str(kb_id)), safe_name)
    abs_path = os.path.join(cfg["UPLOAD_DIR"], rel_path)
    upload_file.save(abs_path)

    conn.execute("UPDATE documents SET file_path=? WHERE id=?", (rel_path, doc_id))
    conn.commit()

    from services.doc_pipeline import process_document

    return process_document(doc_id, kb_id, abs_path, filename)


def delete_document(user: dict, kb_id: int, doc_id: int) -> None:
    kb = get_kb(user, kb_id)
    if not _can_write_kb(user, kb):
        raise ApiError("无权删除该知识库中的文档", 403)
    conn = get_conn()
    row = conn.execute("SELECT * FROM documents WHERE id=? AND kb_id=?", (doc_id, kb_id)).fetchone()
    if not row:
        raise ApiError("文档不存在", 404)

    from extensions import get_vector_store
    from flask import current_app

    store = get_vector_store(current_app.config)
    try:
        store.delete_doc(kb_id, doc_id)
    except Exception:  # noqa: BLE001
        pass
    abs_path = os.path.join(current_app.config["UPLOAD_DIR"], row["file_path"])
    try:
        os.remove(abs_path)
    except OSError:
        pass
    conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    conn.commit()


def search_kb(user: dict, kb_id: int, query: str, k: int = 5) -> list[dict]:
    kb = get_kb(user, kb_id)
    if not can_view_kb(user, kb):
        raise ApiError("无权访问该知识库", 403)
    from flask import current_app
    from services.retriever import retrieve

    hits = retrieve(current_app.config, kb_id, query, top_k=k)
    return [
        {
            "text": h.text,
            "filename": h.filename,
            "chunk_index": h.chunk_index,
            "similarity": round(h.similarity, 4),
            "score": round(h.score, 4),
        }
        for h in hits
    ]
