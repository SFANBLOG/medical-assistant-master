"""聊天路由（FastAPI，含 SSE 流式）。"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse

from backend.services import chat_service
from backend.utils.api_utils import json_body
from backend.utils.jwt_utils import get_current_user

router = APIRouter()


@router.get("/conversations")
def list_conversations(user: dict = Depends(get_current_user)):
    return chat_service.list_conversations(user["user_id"])


@router.post("/conversations")
def create_conversation(user: dict = Depends(get_current_user),
                        data: dict = Depends(json_body)):
    return chat_service.create_conversation(
        user["user_id"],
        kb_id=data.get("kb_id"),
        title=data.get("title", "新对话")
    )


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    conv = chat_service.get_conversation(conv_id, user["user_id"])
    if not conv:
        return JSONResponse({"error": "会话不存在"}, status_code=404)
    return conv


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    ok = chat_service.delete_conversation(conv_id, user["user_id"])
    if not ok:
        return JSONResponse({"error": "会话不存在或无权限"}, status_code=404)
    return {"message": "已删除"}


@router.post("/stream/{conv_id}")
def chat_stream(conv_id: str, user: dict = Depends(get_current_user),
                data: dict = Depends(json_body)):
    """
    SSE 流式问答。

    请求体: {"question": "...", "kb_id": null}
    响应: SSE 流
    """
    question = (data.get("question") or "").strip()
    kb_id = data.get("kb_id")

    if not question:
        return JSONResponse({"error": "问题不能为空"}, status_code=400)

    # 验证会话归属
    conv = chat_service.get_conversation(conv_id, user["user_id"])
    if not conv:
        return JSONResponse({"error": "会话不存在"}, status_code=404)

    # 同步生成器直接交给 StreamingResponse：Starlette 会在线程池里迭代它，
    # 不会阻塞事件循环（与保留同步 chat_service/RAG 层的设计一致）。
    return StreamingResponse(
        chat_service.chat_stream_sse(
            conv_id=conv_id,
            user_id=user["user_id"],
            role=user["role"],
            question=question,
            kb_id=kb_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/history")
def chat_history(user: dict = Depends(get_current_user), limit: int = Query(50)):
    return chat_service.get_chat_history(user["user_id"], limit)
