"""知识库路由"""
from flask import Blueprint, request, jsonify

from backend.utils.jwt_utils import login_required, current_user, role_required
from backend.services import kb_service

kb_bp = Blueprint("kb", __name__)


@kb_bp.route("/", methods=["GET"])
@login_required
def list_kb():
    user = current_user()
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)
    result = kb_service.list_knowledge_bases(user["role"], user["user_id"], page, size)
    return jsonify(result)


@kb_bp.route("/", methods=["POST"])
@role_required("doctor", "admin")
def create_kb():
    user = current_user()
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    description = data.get("description", "")
    visibility = data.get("visibility", "private")

    if not name:
        return jsonify({"error": "知识库名称不能为空"}), 400

    result = kb_service.create_knowledge_base(
        owner_id=user["user_id"],
        name=name,
        description=description,
        visibility=visibility
    )
    return jsonify(result)


@kb_bp.route("/<int:kb_id>", methods=["DELETE"])
@role_required("doctor", "admin")
def delete_kb(kb_id):
    ok = kb_service.delete_knowledge_base(kb_id)
    if not ok:
        return jsonify({"error": "知识库不存在"}), 404
    return jsonify({"message": "已删除"})


@kb_bp.route("/<int:kb_id>/documents", methods=["GET"])
@login_required
def list_documents(kb_id):
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)
    result = kb_service.list_documents(kb_id, page, size)
    return jsonify(result)


@kb_bp.route("/<int:kb_id>/documents", methods=["POST"])
@role_required("doctor", "admin")
def upload_document(kb_id):
    """上传文档（multipart/form-data）。"""
    user = current_user()

    if "file" not in request.files:
        return jsonify({"error": "未上传文件"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "文件名为空"}), 400

    visibility = request.form.get("visibility", "public")

    # 读取文件内容
    content_bytes = file.read()

    result = kb_service.upload_document(
        kb_id=kb_id,
        file_path=file.filename,
        filename=file.filename,
        visibility=visibility,
        content_bytes=content_bytes,
        uploader_id=user["user_id"],
        uploader_role=user["role"],
    )

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@kb_bp.route("/<int:kb_id>/documents/batch", methods=["POST"])
@role_required("doctor", "admin")
def upload_documents_batch(kb_id):
    """批量上传文档（multipart/form-data，files 字段可重复出现）。

    - 每个文件独立处理，单个失败不阻塞其它文件
    - 单次请求总大小受 Flask MAX_CONTENT_LENGTH 限制（默认 64MB）
    - 每文件最多 200 个，0 个文件返回 400
    """
    user = current_user()

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "未选择任何文件"}), 400

    if len(files) > 200:
        return jsonify({"error": f"单次最多上传 200 个文件，当前 {len(files)} 个"}), 400

    visibility = request.form.get("visibility", "public")

    result = kb_service.upload_documents_batch(
        kb_id=kb_id,
        files=files,
        visibility=visibility,
        uploader_id=user["user_id"],
        uploader_role=user["role"],
    )
    return jsonify(result)


@kb_bp.route("/documents/<int:doc_id>", methods=["DELETE"])
@role_required("doctor", "admin")
def delete_document(doc_id):
    ok = kb_service.delete_document(doc_id)
    if not ok:
        return jsonify({"error": "文档不存在"}), 404
    return jsonify({"message": "已删除"})
