"""
RAG 编排（Retrieval-Augmented Generation）
==================================================================
查询 → 按角色过滤召回 → 上下文构建 → 大模型流式回答 → 保存引用来源。
以生成器形式产出 SSE 事件，供 chat API 直接流式推送。
"""
import json
import uuid

from models import db
from services import llm as llm_svc
from services.retriever import retrieve


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def answer(user_id: int, role: str, question: str, kb_id: int = None):
    """生成器：逐个产出 SSE 事件字符串。"""
    # 1) 检索
    chunks = retrieve(question, role, kb_id=kb_id)
    # 仅保留可追溯的引用信息
    citations_view = [{
        "title": c.get("title", ""),
        "similarity": c.get("similarity", 0.0),
        "doc_id": c.get("doc_id"),
        "kb_id": c.get("kb_id"),
        "chunk_index": c.get("chunk_index"),
        "snippet": (c.get("text", "") or "")[:240],
    } for c in chunks]
    yield _sse({"type": "retrieval", "chunks": citations_view})

    # 2) 会话与消息落库
    conv_id = uuid.uuid4().hex
    title = (question or "咨询").strip().replace("\n", " ")[:60]
    db.execute(
        "INSERT INTO conversations (id, user_id, kb_id, title) VALUES (%s, %s, %s, %s)",
        (conv_id, user_id, kb_id, title),
    )
    db.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'user', %s)",
        (conv_id, question),
    )

    # 3) 流式生成
    llm = llm_svc.LLMService()
    full = []
    for tok in llm.stream(question, chunks):
        full.append(tok)
        yield _sse({"type": "token", "content": tok})

    answer_text = "".join(full)

    # 4) 保存回答与引用
    msg_id = db.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'assistant', %s)",
        (conv_id, answer_text),
    )
    for c in chunks:
        db.execute(
            "INSERT INTO citations (message_id, document_id, chunk_index, source_text, title, similarity) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (msg_id, c.get("doc_id"), c.get("chunk_index"),
             (c.get("text", "") or "")[:1000], c.get("title", ""), c.get("similarity", 0.0)),
        )
    db.execute("UPDATE conversations SET updated_at=NOW() WHERE id=%s" if db.DB_TYPE_EFFECTIVE == "mysql"
               else "UPDATE conversations SET updated_at=datetime('now') WHERE id=%s", (conv_id,))

    yield _sse({"type": "done", "conversation_id": conv_id, "message_id": msg_id,
                "citations": citations_view})
