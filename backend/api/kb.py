from flask import Blueprint, g, request

from api.decorators import require_auth, require_roles
from services import kb_service
from utils.errors import ApiError

kb_bp = Blueprint("kb", __name__)


@kb_bp.get("")
@require_auth
def list_kbs():
    return {"items": kb_service.list_kbs(g.user)}


@kb_bp.post("")
@require_roles("doctor", "admin")
def create_kb():
    data = request.get_json(silent=True) or {}
    kb = kb_service.create_kb(
        g.user,
        name=data.get("name", ""),
        description=data.get("description", ""),
        visibility=data.get("visibility", "private"),
    )
    return kb, 201


@kb_bp.get("/<int:kb_id>")
@require_auth
def get_kb(kb_id: int):
    return kb_service.get_kb(g.user, kb_id)


@kb_bp.delete("/<int:kb_id>")
@require_auth
def delete_kb(kb_id: int):
    kb_service.delete_kb(g.user, kb_id)
    return {"ok": True}


@kb_bp.get("/<int:kb_id>/documents")
@require_auth
def list_documents(kb_id: int):
    return {"items": kb_service.list_documents(g.user, kb_id)}


@kb_bp.post("/<int:kb_id>/documents")
@require_auth
def upload_document(kb_id: int):
    file = request.files.get("file")
    if not file:
        raise ApiError("未上传文件", 400)
    doc = kb_service.add_document(g.user, kb_id, file)
    return doc, 201


@kb_bp.delete("/<int:kb_id>/documents/<int:doc_id>")
@require_auth
def delete_document(kb_id: int, doc_id: int):
    kb_service.delete_document(g.user, kb_id, doc_id)
    return {"ok": True}


@kb_bp.get("/<int:kb_id>/search")
@require_auth
def search_kb(kb_id: int):
    q = request.args.get("q", "")
    k = min(int(request.args.get("k", "5")), 20)
    if not q:
        raise ApiError("缺少搜索关键词 q", 400)
    return {"items": kb_service.search_kb(g.user, kb_id, q, k)}
