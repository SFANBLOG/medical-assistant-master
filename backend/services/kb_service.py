"""知识库与文档服务：角色权限 + 公开/私有 权限模型。

角色权限（依据安医大附属医院 RAG 系统角色划分）：
- 医生 / 管理员：可创建知识库、上传/管理文档（管理员可管理全部，医生可管理
  公开知识库及自己创建的私有知识库）；
- 患者 / 护士 / 群众：只能基于「公开知识库 + 公开文档」进行查询，不可创建或管理。

文档可见性：
- 公开文档：存于 uploads/<知识库>/公开/，所有可访问该知识库的用户可见；
- 私有文档：存于 uploads/<知识库>/私有/，仅医生 / 管理员可见（患者/群众/护士
  查询时不会检索到）。
"""
import os
import uuid

from models.db import get_conn
from utils.errors import ApiError

PUBLIC_DIR = "公开"
PRIVATE_DIR = "私有"


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


def can_view_private_docs(user: dict) -> bool:
    """患者 / 群众 / 护士只能看到公开文档。"""
    return user["role"] in ("doctor", "admin")


def list_visible_kb_ids(user: dict) -> list[int]:
    """当前用户可见且至少含一个可见文档的知识库 id 列表（用于跨知识库检索）。

    仅返回有文档的知识库，避免对空知识库做无意义的向量检索。
    """
    conn = get_conn()
    if user["role"] == "admin":
        kb_where, kb_params = "1=1", []
    else:
        kb_where, kb_params = "(k.visibility = 'public' OR k.owner_id = ?)", [user["id"]]
    if can_view_private_docs(user):
        doc_where, doc_params = "1=1", []
    else:
        doc_where, doc_params = "d.visibility = 'public'", []
    rows = conn.execute(
        f"""SELECT DISTINCT k.id FROM knowledge_bases k
            JOIN documents d ON d.kb_id = k.id
            WHERE {kb_where} AND {doc_where}
            ORDER BY k.id""",
        kb_params + doc_params,
    ).fetchall()
    return [r["id"] for r in rows]


def list_known_doc_names(user: dict) -> list[str]:
    """当前用户可见文档的标题列表（疾病名），供提问中的疾病名提取使用。"""
    conn = get_conn()
    if can_view_private_docs(user):
        where, params = "1=1", []
    else:
        where, params = "visibility = 'public'", []
    rows = conn.execute(
        f"SELECT filename FROM documents WHERE {where}", params
    ).fetchall()
    names = set()
    for r in rows:
        name = os.path.splitext(r["filename"])[0].strip()
        if name:
            names.add(name)
    return sorted(names)


def can_upload_doc(user: dict, kb: dict) -> bool:
    """上传文档权限：管理员任意；医生可上传到公开知识库或自己的私有知识库。"""
    if user["role"] == "admin":
        return True
    if user["role"] != "doctor":
        return False
    return kb["visibility"] == "public" or kb["owner_id"] == user["id"]


def _doc_scope(user: dict) -> tuple[str, list]:
    """返回文档可见性过滤 SQL（供列表 / 计数使用）。"""
    if can_view_private_docs(user):
        return "1=1", []
    return "d.visibility = 'public'", []


def list_kbs(user: dict) -> list[dict]:
    conn = get_conn()
    if user["role"] == "admin":
        where, params = "1=1", []
    else:
        where, params = "(k.visibility = 'public' OR k.owner_id = ?)", [user["id"]]
    doc_where, doc_params = _doc_scope(user)
    rows = conn.execute(
        f"""SELECT k.id, k.name, k.description, k.visibility, k.owner_id, k.created_at,
                  u.display_name AS owner_name,
                  (SELECT COUNT(*) FROM documents d WHERE d.kb_id = k.id AND {doc_where}) AS doc_count,
                  (SELECT COALESCE(SUM(d.chunk_count),0) FROM documents d
                     WHERE d.kb_id = k.id AND {doc_where}) AS chunk_count
           FROM knowledge_bases k
           LEFT JOIN users u ON u.id = k.owner_id
           WHERE {where}
           ORDER BY k.created_at DESC""",
        params + doc_params,
    ).fetchall()
    items = []
    for r in rows:
        row = dict(r)
        row["chunk_count"] = int(row["chunk_count"] or 0)  # MySQL SUM 返回 Decimal，统一转 int
        items.append(row)
    return items


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
    doc_where, doc_params = _doc_scope(user)
    kb["doc_count"] = conn.execute(
        f"SELECT COUNT(*) FROM documents d WHERE d.kb_id = ? AND {doc_where}", (kb_id,) + tuple(doc_params)
    ).fetchone()[0]
    return kb


def delete_kb(user: dict, kb_id: int) -> None:
    kb = get_kb(user, kb_id)
    if not can_delete_kb(user, kb):
        raise ApiError("无权删除该知识库", 403)
    # 删除向量库集合（Milvus / NumpyStore）
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
    kb = get_kb(user, kb_id)  # 权限校验
    conn = get_conn()
    doc_where, doc_params = _doc_scope(user)
    rows = conn.execute(
        f"""SELECT * FROM documents d WHERE d.kb_id = ? AND {doc_where}
            ORDER BY d.created_at DESC, d.id DESC""",
        (kb_id,) + tuple(doc_params),
    ).fetchall()
    return [dict(r) for r in rows]


def _visibility_dir(visibility: str) -> str:
    return PUBLIC_DIR if visibility == "public" else PRIVATE_DIR


def add_document(user: dict, kb_id: int, upload_file, visibility: str = "") -> dict:
    """上传文档：落盘到 uploads/<知识库>/公开|私有/ 目录并向量化入库。

    处理失败不再抛出 500，而是返回 status='failed' 且带 error 信息的文档行，
    便于前端展示具体原因并允许删除（解决上传出错不可控的问题）。
    """
    from flask import current_app

    cfg = current_app.config
    kb = get_kb(user, kb_id)
    if not can_upload_doc(user, kb):
        raise ApiError("无权向该知识库上传文档", 403)

    visibility = visibility or kb["visibility"]
    if visibility not in ("public", "private"):
        raise ApiError("无效的文档可见性", 400)

    filename = upload_file.filename or ""
    if not filename:
        raise ApiError("文件名为空，请重新选择文件", 400)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in cfg["ALLOWED_EXTENSIONS"]:
        raise ApiError(f"不支持的文件类型：仅支持 {', '.join(sorted(cfg['ALLOWED_EXTENSIONS']))}", 400)

    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO documents (kb_id, filename, file_path, file_type, visibility, status)
           VALUES (?, ?, ?, ?, ?, 'processing')""",
        (kb_id, filename, "", ext.lstrip("."), visibility),
    )
    doc_id = cur.lastrowid
    conn.commit()

    # 落盘：UPLOAD_DIR/<知识库名>/公开|私有/<uuid>_<filename>
    from utils.file_utils import safe_folder_name

    kb_folder = safe_folder_name(kb["name"], str(kb_id))
    sub_dir = _visibility_dir(visibility)
    kb_dir = os.path.join(cfg["UPLOAD_DIR"], kb_folder, sub_dir)
    os.makedirs(kb_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:12]}_{os.path.basename(filename)}"
    rel_path = os.path.join(kb_folder, sub_dir, safe_name)
    abs_path = os.path.join(cfg["UPLOAD_DIR"], rel_path)
    upload_file.save(abs_path)

    conn.execute("UPDATE documents SET file_path=? WHERE id=?", (rel_path, doc_id))
    conn.commit()

    from services.doc_pipeline import process_document

    try:
        return process_document(doc_id, kb_id, abs_path, filename, visibility)
    except Exception as e:  # noqa: BLE001
        # 向量化/文本抽取失败：保留文档行与文件，置 failed 并返回详细信息
        row = dict(conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())
        row["error"] = f"文档处理失败：{str(e)[:300]}"
        return row


def delete_document(user: dict, kb_id: int, doc_id: int) -> None:
    kb = get_kb(user, kb_id)
    if not can_upload_doc(user, kb):
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

    allow_private = can_view_private_docs(user)
    kb_ids = list_visible_kb_ids(user)
    hits = retrieve(
        current_app.config, kb_ids, query, top_k=k,
        allow_private=allow_private, bias_kb_id=kb_id,
        known_names=list_known_doc_names(user),
    )
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
