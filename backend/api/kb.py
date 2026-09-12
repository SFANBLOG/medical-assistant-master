"""知识库接口：列表 / 创建 / 上传文档 / 重新索引。"""
import os
import re
import uuid

from flask import Blueprint, request, current_app

import config as cfg
from models import db
from services import kb_service
from api.common import ok, fail, token_required, role_required, current_user

kb_bp = Blueprint("kb", __name__, url_prefix="/api/kb")


def _safe_name(name: str) -> str:
    name = name.strip().replace(" ", "_")
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name or ("file_" + uuid.uuid4().hex[:8])


@kb_bp.route("/list", methods=["GET"])
@token_required
def list_kb():
    u = current_user()
    can_private = u["role"] in cfg.PRIVATE_VIEW_ROLES
    rows = db.query(
        "SELECT kb.*, (SELECT COUNT(*) FROM documents d WHERE d.kb_id=kb.id) AS doc_count "
        "FROM knowledge_bases kb ORDER BY kb.id"
    )
    if not can_private:
        rows = [r for r in rows if r["visibility"] == "public"]
    return ok(rows)


@kb_bp.route("/create", methods=["POST"])
@role_required("doctor", "admin")
def create_kb():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return fail("知识库名称不能为空")
    visibility = body.get("visibility", "private")
    desc = body.get("description", "")
    uid = current_user()["id"]
    kb_id = db.execute(
        "INSERT INTO knowledge_bases (owner_id, name, description, visibility) VALUES (%s, %s, %s, %s)",
        (uid if current_user()["role"] == "doctor" else None, name, desc, visibility),
    )
    # 创建公开/私有目录
    for sub in (cfg.PUBLIC_DIR, cfg.PRIVATE_DIR):
        os.makedirs(cfg.UPLOAD_DIR / name / sub, exist_ok=True)
    return ok({"id": kb_id, "name": name})


@kb_bp.route("/upload", methods=["POST"])
@role_required("doctor", "admin")
def upload():
    u = current_user()
    kb_id = request.form.get("kb_id") or request.form.get("kbId")
    visibility = request.form.get("visibility", "public")
    file = request.files.get("file")
    if not kb_id or not file:
        return fail("缺少知识库或文件")
    kb = db.query_one("SELECT * FROM knowledge_bases WHERE id=%s", (kb_id,))
    if not kb:
        return fail("知识库不存在")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in cfg.ALLOWED_EXT:
        return fail(f"不支持的格式：{ext}（仅支持 txt/md/pdf/docx/pptx）", 415)
    # 医生上传私有文档：仅本人可见；管理员无限制。此处按提交可见性落盘。
    sub = cfg.PRIVATE_DIR if visibility == "private" else cfg.PUBLIC_DIR
    kb_name = _safe_name(kb["name"])
    save_dir = cfg.UPLOAD_DIR / kb_name / sub
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_name(file.filename)
    if not filename.lower().endswith(ext):
        filename += ext
    saved_file = save_dir / filename
    try:
        file.save(str(saved_file))
    except Exception as e:
        return fail(f"文件保存失败：{e}", 500)

    rel_path = f"{kb_name}/{sub}/{filename}"
    doc_id = kb_service.upload_document(
        int(kb_id), filename, rel_path, visibility, ext.lstrip("."))
    # 异步式处理（同步执行，文件较小）
    success = kb_service.process_document(doc_id)
    doc = db.query_one("SELECT * FROM documents WHERE id=%s", (doc_id,))
    if not success:
        return ok({"id": doc_id, "status": doc["status"], "error": doc.get("error")},
                  warning="文档已上传但处理失败")
    return ok({"id": doc_id, "status": "ready", "chunk_count": doc["chunk_count"]})


@kb_bp.route("/documents", methods=["GET"])
@token_required
def documents():
    kb_id = request.args.get("kb_id")
    if kb_id:
        rows = db.query("SELECT * FROM documents WHERE kb_id=%s ORDER BY id", (kb_id,))
    else:
        rows = db.query("SELECT * FROM documents ORDER BY id")
    return ok(rows)


@kb_bp.route("/reindex", methods=["POST"])
@role_required("doctor", "admin")
def reindex():
    n = kb_service.reindex_all()
    return ok({"indexed": n})
