"""
知识库服务：知识库 CRUD、文档上传/切分/向量化/检索。
"""
import shutil

from backend import config
from backend.rag.chunker import chunk_document
from backend.rag.embedder import get_embedder
from backend.rag.vectorstore import get_vectorstore, VectorRecord
from backend.utils.db import fetchone, fetchall, execute, DB_TYPE
from backend.utils.file_parser import (
    parse_file,
    parse_file_pages,
    strip_header_footer,
    get_file_type,
    is_allowed,
    get_ext,
)


def list_knowledge_bases(role: str, user_id: int, page: int = 1, size: int = 20) -> dict:
    """获取知识库列表（按角色权限过滤）。"""
    offset = (page - 1) * size
    ph = "%s" if DB_TYPE == "mysql" else "?"

    if role == "admin":
        # 管理员可见全部
        total = fetchone("SELECT COUNT(*) AS cnt FROM knowledge_bases")["cnt"]
        rows = fetchall(
            f"SELECT k.*, u.display_name AS owner_name, "
            f"(SELECT COUNT(*) FROM documents WHERE kb_id = k.id) AS doc_count "
            f"FROM knowledge_bases k LEFT JOIN users u ON k.owner_id = u.id "
            f"ORDER BY k.id DESC LIMIT {ph} OFFSET {ph}",
            (size, offset)
        )
    elif role == "doctor":
        # 医生可见公开 + 自己的私有
        total = fetchone(
            "SELECT COUNT(*) AS cnt FROM knowledge_bases WHERE visibility = 'public' "
            "OR owner_id = %s",
            (user_id,)
        )["cnt"]
        rows = fetchall(
            f"SELECT k.*, u.display_name AS owner_name, "
            f"(SELECT COUNT(*) FROM documents WHERE kb_id = k.id) AS doc_count "
            f"FROM knowledge_bases k LEFT JOIN users u ON k.owner_id = u.id "
            f"WHERE k.visibility = 'public' OR k.owner_id = %s "
            f"ORDER BY k.id DESC LIMIT {ph} OFFSET {ph}",
            (user_id, size, offset)
        )
    else:
        # 其他角色仅可见公开
        total = fetchone("SELECT COUNT(*) AS cnt FROM knowledge_bases WHERE visibility = 'public'")["cnt"]
        rows = fetchall(
            f"SELECT k.*, u.display_name AS owner_name, "
            f"(SELECT COUNT(*) FROM documents WHERE kb_id = k.id) AS doc_count "
            f"FROM knowledge_bases k LEFT JOIN users u ON k.owner_id = u.id "
            f"WHERE k.visibility = 'public' "
            f"ORDER BY k.id DESC LIMIT {ph} OFFSET {ph}",
            (size, offset)
        )

    return {"total": total, "list": rows, "page": page, "size": size}


def create_knowledge_base(owner_id: int, name: str, description: str, visibility: str) -> dict:
    """创建知识库。"""
    execute(
        "INSERT INTO knowledge_bases (owner_id, name, description, visibility) VALUES (%s, %s, %s, %s)",
        (owner_id if visibility == "private" else None, name, description, visibility)
    )
    kb = fetchone("SELECT * FROM knowledge_bases WHERE name = %s ORDER BY id DESC LIMIT 1", (name,))
    return kb


def delete_knowledge_base(kb_id: int) -> bool:
    """删除知识库（含文档与向量）。

    物理文件删除失败不会阻断逻辑删除。
    """
    kb = fetchone("SELECT * FROM knowledge_bases WHERE id = %s", (kb_id,))
    if not kb:
        return False

    # 删除向量
    try:
        vs = get_vectorstore()
        vs.delete_by_kb(kb_id)
    except Exception as e:
        print(f"[KB] 删除向量失败: {e}")

    # 删除文件（失败不阻断）
    try:
        kb_dir = config.UPLOAD_DIR / kb["name"]
        if kb_dir.exists():
            shutil.rmtree(kb_dir, ignore_errors=True)
    except Exception as e:
        print(f"[KB] 删除知识库目录失败（忽略）: {e}")

    # 删除数据库记录
    execute("DELETE FROM documents WHERE kb_id = %s", (kb_id,))
    execute("DELETE FROM knowledge_bases WHERE id = %s", (kb_id,))
    return True


def _extract_document_text(path: str, file_type: str) -> str:
    """
    按格式提取纯文本。

    PDF 走专用路径：逐页提取（无文本层时自动 OCR）-> 空文本检测
    -> 清洗页眉/页脚/页码，再把各页用空行拼接交给切分器；其它格式直接整体解析。
    """
    if file_type != "pdf":
        return parse_file(path)

    pages = parse_file_pages(path)
    total_chars = sum(len(t.strip()) for _, t in pages)
    if total_chars < config.PDF_MIN_TEXT_CHARS:
        raise ValueError(
            "PDF 未提取到任何文本（扫描件需 OCR 支持，图片型 PDF 请提供更清晰的版本）"
        )

    if config.PDF_STRIP_HEADER_FOOTER:
        pages = strip_header_footer(pages)
    return "\n\n".join(t for _, t in pages)


def upload_document(
        kb_id: int,
        file_path: str,
        filename: str,
        visibility: str,
        content_bytes: bytes = None,
) -> dict:
    """
    上传文档到知识库。

    file_path 可以是已存在的文件路径，或配合 content_bytes 写入新文件。
    """
    kb = fetchone("SELECT * FROM knowledge_bases WHERE id = %s", (kb_id,))
    if not kb:
        return {"error": "知识库不存在"}

    # 扩展名白名单校验：不支持的格式在落盘前直接拒绝
    if not is_allowed(filename):
        return {"error": f"不支持的文件格式：.{get_ext(filename) or '未知'}"}

    # 确定保存路径
    vis_folder = "公开" if visibility == "public" else "私有"
    save_dir = config.UPLOAD_DIR / kb["name"] / vis_folder
    save_dir.mkdir(parents=True, exist_ok=True)

    save_path = save_dir / filename
    file_type = get_file_type(filename)

    # 写入文件
    if content_bytes:
        with open(save_path, "wb") as f:
            f.write(content_bytes)
    elif not save_path.exists():
        return {"error": "文件不存在"}

    # 解析文本（PDF 走分页 + 页眉页脚清洗的专用路径）
    try:
        text = _extract_document_text(str(save_path), file_type)
        if not text.strip():
            return {"error": "文件内容为空"}
    except ValueError as e:
        # 扫描件等「可预期」的解析失败：明确提示，不记为 failed
        return {"error": str(e)}
    except Exception as e:
        # 更新状态为 failed
        execute(
            "INSERT INTO documents (kb_id, filename, file_path, file_type, visibility, status, error) "
            "VALUES (%s, %s, %s, %s, %s, 'failed', %s)",
            (kb_id, filename, f"{kb['name']}/{vis_folder}/{filename}", file_type, visibility, str(e)[:500])
        )
        return {"error": f"文件解析失败: {e}"}

    # 切分
    chunks = chunk_document(text)
    if not chunks:
        return {"error": "文档切分结果为空"}

    # 向量化
    embedder = get_embedder()
    chunk_texts = [c.text for c in chunks]
    embeddings = embedder.embed_batch(chunk_texts)

    # 先注册文档（拿到 doc_id，再写入向量）
    rel_path = f"{kb['name']}/{vis_folder}/{filename}"
    execute(
        "INSERT INTO documents (kb_id, filename, file_path, file_type, visibility, chunk_count, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'ready')",
        (kb_id, filename, rel_path, file_type, visibility, len(chunks))
    )
    doc = fetchone("SELECT id FROM documents WHERE file_path = %s ORDER BY id DESC LIMIT 1", (rel_path,))

    # 写入向量：每条 chunk 关联到 doc_id
    vs = get_vectorstore()
    records = [
        VectorRecord(
            id=f"doc{doc['id']}_chunk{chunk.index}",
            kb_id=kb_id,
            doc_id=doc["id"],
            chunk_index=chunk.index,
            text=chunk.text,
            embedding=emb.tolist(),
        )
        for chunk, emb in zip(chunks, embeddings)
    ]
    if records:
        vs.insert_batch(records)

    return {
        "doc_id": doc["id"],
        "filename": filename,
        "chunk_count": len(chunks),
        "status": "ready",
    }


def list_documents(kb_id: int, page: int = 1, size: int = 20) -> dict:
    """获取知识库文档列表。"""
    offset = (page - 1) * size
    total = fetchone("SELECT COUNT(*) AS cnt FROM documents WHERE kb_id = %s", (kb_id,))["cnt"]
    rows = fetchall(
        "SELECT * FROM documents WHERE kb_id = %s ORDER BY id DESC LIMIT %s OFFSET %s",
        (kb_id, size, offset)
    )
    return {"total": total, "list": rows, "page": page, "size": size}


def upload_documents_batch(
        kb_id: int,
        files,
        visibility: str,
        uploader_id: int = None,
        uploader_role: str = None,
) -> dict:
    """批量上传文档到知识库。

    - 每个文件独立处理，单个失败不阻塞其它文件
    - files: Flask FileStorage 列表（request.files.getlist("files")）
    - 返回结构：
        {
          "results": [
            {"filename": str, "ok": bool,
             "doc_id"?: int, "chunk_count"?: int, "status"?: str,
             "error"?: str},
            ...
          ],
          "summary": {"total": N, "success": S, "failed": F}
        }
    """
    # 一次 404 检测，避免每个文件都重复查
    kb = fetchone("SELECT * FROM knowledge_bases WHERE id = %s", (kb_id,))
    if not kb:
        return {
            "results": [{"filename": f.filename or "?", "ok": False, "error": "知识库不存在"}
                        for f in files],
            "summary": {"total": len(files), "success": 0, "failed": len(files)},
        }

    results = []
    success = failed = 0
    for f in files:
        filename = f.filename or "(未命名)"
        try:
            content_bytes = f.read()
            r = upload_document(
                kb_id=kb_id,
                file_path=filename,
                filename=filename,
                visibility=visibility,
                content_bytes=content_bytes,
            )
            if "error" in r:
                results.append({"filename": filename, "ok": False, "error": r["error"]})
                failed += 1
            else:
                results.append({
                    "filename": filename,
                    "ok": True,
                    "doc_id": r["doc_id"],
                    "chunk_count": r["chunk_count"],
                    "status": r["status"],
                })
                success += 1
        except Exception as e:  # noqa: BLE001
            # 单文件异常不阻断其它
            results.append({
                "filename": filename,
                "ok": False,
                "error": f"上传异常: {type(e).__name__}: {str(e)[:200]}",
            })
            failed += 1

    return {
        "results": results,
        "summary": {"total": len(files), "success": success, "failed": failed},
    }


def delete_document(doc_id: int) -> bool:
    """删除文档（含向量与文件）。

    物理文件删除失败不会阻断逻辑删除（向量 + 数据库记录）。
    """
    doc = fetchone("SELECT * FROM documents WHERE id = %s", (doc_id,))
    if not doc:
        return False

    # 1. 删除向量
    try:
        vs = get_vectorstore()
        vs.delete_by_doc(doc_id)
    except Exception as e:
        print(f"[KB] 删除向量失败: {e}")

    # 2. 删除物理文件（失败不阻断）
    try:
        file_path = config.UPLOAD_DIR / doc["file_path"]
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        print(f"[KB] 删除物理文件失败（忽略）: {e}")

    # 3. 删除数据库记录
    execute("DELETE FROM citations WHERE document_id = %s", (doc_id,))
    execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    return True
