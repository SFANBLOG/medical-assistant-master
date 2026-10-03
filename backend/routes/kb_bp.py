"""知识库路由（FastAPI APIRouter）。"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse

from backend.services import kb_service
from backend.utils.api_utils import json_body
from backend.utils.jwt_utils import get_current_user, require_roles

router = APIRouter()


class _FileShim:
    """把 FastAPI UploadFile 适配成 kb_service 期望的同步文件对象。

    服务层沿用 Flask 语义直接调用 f.filename 与 f.read()（同步），
    这里把 UploadFile 的底层 SpooledTemporaryFile(.file) 暴露为同步 read()。
    """

    def __init__(self, upload: UploadFile):
        self._upload = upload
        self.filename = upload.filename

    def read(self) -> bytes:
        return self._upload.file.read()


@router.get("/")
def list_kb(user: dict = Depends(get_current_user),
            page: int = Query(1), size: int = Query(20)):
    return kb_service.list_knowledge_bases(user["role"], user["user_id"], page, size)


@router.post("/")
def create_kb(user: dict = Depends(require_roles("doctor", "admin")),
              data: dict = Depends(json_body)):
    name = (data.get("name") or "").strip()
    description = data.get("description", "")
    visibility = data.get("visibility", "private")

    if not name:
        return JSONResponse({"error": "知识库名称不能为空"}, status_code=400)

    return kb_service.create_knowledge_base(
        owner_id=user["user_id"],
        name=name,
        description=description,
        visibility=visibility
    )


@router.delete("/{kb_id}")
def delete_kb(kb_id: int, user: dict = Depends(require_roles("doctor", "admin"))):
    ok = kb_service.delete_knowledge_base(kb_id)
    if not ok:
        return JSONResponse({"error": "知识库不存在"}, status_code=404)
    return {"message": "已删除"}


@router.get("/{kb_id}/documents")
def list_documents(kb_id: int, user: dict = Depends(get_current_user),
                   page: int = Query(1), size: int = Query(20)):
    return kb_service.list_documents(kb_id, page, size)


@router.post("/{kb_id}/documents")
def upload_document(kb_id: int, user: dict = Depends(require_roles("doctor", "admin")),
                    file: UploadFile | None = File(default=None),
                    visibility: str = Form("public")):
    """上传文档（multipart/form-data）。"""
    if file is None:
        return JSONResponse({"error": "未上传文件"}, status_code=400)
    if not file.filename:
        return JSONResponse({"error": "文件名为空"}, status_code=400)

    content_bytes = file.file.read()

    result = kb_service.upload_document(
        kb_id=kb_id,
        file_path=file.filename,
        filename=file.filename,
        visibility=visibility,
        content_bytes=content_bytes,
    )

    if "error" in result:
        return JSONResponse(result, status_code=400)
    return result


@router.post("/{kb_id}/documents/batch")
def upload_documents_batch(kb_id: int, user: dict = Depends(require_roles("doctor", "admin")),
                           files: list[UploadFile] | None = File(default=None),
                           visibility: str = Form("public")):
    """批量上传文档（multipart/form-data，files 字段可重复出现）。

    - 每个文件独立处理，单个失败不阻塞其它文件
    - 每文件最多 200 个，0 个文件返回 400
    """
    files = files or []
    if not files:
        return JSONResponse({"error": "未选择任何文件"}, status_code=400)

    if len(files) > 200:
        return JSONResponse({"error": f"单次最多上传 200 个文件，当前 {len(files)} 个"}, status_code=400)

    result = kb_service.upload_documents_batch(
        kb_id=kb_id,
        files=[_FileShim(f) for f in files],
        visibility=visibility,
        uploader_id=user["user_id"],
        uploader_role=user["role"],
    )
    return result


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, user: dict = Depends(require_roles("doctor", "admin"))):
    ok = kb_service.delete_document(doc_id)
    if not ok:
        return JSONResponse({"error": "文档不存在"}, status_code=404)
    return {"message": "已删除"}
