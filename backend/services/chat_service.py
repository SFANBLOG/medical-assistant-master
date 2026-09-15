"""
聊天服务：会话管理 + SSE 流式问答。
"""
import uuid
from typing import Generator

from backend.rag.llm import chat_stream, _clean_answer_text
from backend.rag.retriever import retrieve, build_context
from backend.utils.db import fetchone, fetchall, execute, NOW_SQL


def create_conversation(user_id: int, kb_id: int = None, title: str = "新对话") -> dict:
    """创建新会话。"""
    conv_id = uuid.uuid4().hex
    execute(
        "INSERT INTO conversations (id, user_id, kb_id, title) VALUES (%s, %s, %s, %s)",
        (conv_id, user_id, kb_id, title[:128])
    )
    return {"id": conv_id, "title": title}


def list_conversations(user_id: int) -> list[dict]:
    """获取用户的会话列表。"""
    rows = fetchall(
        "SELECT c.*, k.name AS kb_name "
        "FROM conversations c LEFT JOIN knowledge_bases k ON c.kb_id = k.id "
        "WHERE c.user_id = %s ORDER BY c.updated_at DESC",
        (user_id,)
    )
    return rows


def _attach_citations_batch(messages: list[dict], order: str = "id") -> None:
    """为一批消息一次性补齐引用来源（单条 IN 查询，替代逐条查询）。

    order="id" 保持引用插入顺序；order="similarity" 按相似度降序。
    """
    ids = [m["id"] for m in messages if m.get("role") == "assistant" and m.get("id")]
    if not ids:
        for m in messages:
            m["citations"] = []
        return
    order_sql = "similarity DESC" if order == "similarity" else "id ASC"
    placeholders = ",".join(["%s"] * len(ids))
    rows = fetchall(
        "SELECT message_id, document_id AS doc_id, chunk_index, source_text, title, similarity "
        f"FROM citations WHERE message_id IN ({placeholders}) ORDER BY {order_sql}",
        tuple(ids),
    )
    by_msg: dict = {}
    for r in rows:
        by_msg.setdefault(r["message_id"], []).append(r)
    for m in messages:
        if m.get("role") == "assistant":
            m["citations"] = by_msg.get(m.get("id"), [])
        else:
            m["citations"] = []


def get_conversation(conv_id: str, user_id: int) -> dict | None:
    """获取会话详情（含消息及每条 AI 回答的引用来源）。"""
    conv = fetchone("SELECT * FROM conversations WHERE id = %s AND user_id = %s", (conv_id, user_id))
    if not conv:
        return None
    messages = fetchall(
        "SELECT * FROM messages WHERE conversation_id = %s ORDER BY id ASC",
        (conv_id,)
    )
    # 为 AI 回答补齐引用来源（citations），让历史会话也能展示「相关文档」
    _attach_citations_batch(messages)
    conv["messages"] = messages
    return conv


def delete_conversation(conv_id: str, user_id: int) -> bool:
    """删除会话。"""
    conv = fetchone("SELECT id FROM conversations WHERE id = %s AND user_id = %s", (conv_id, user_id))
    if not conv:
        return False
    execute("DELETE FROM citations WHERE message_id IN (SELECT id FROM messages WHERE conversation_id = %s)", (conv_id,))
    execute("DELETE FROM messages WHERE conversation_id = %s", (conv_id,))
    execute("DELETE FROM conversations WHERE id = %s", (conv_id,))
    return True


def chat_stream_sse(
    conv_id: str,
    user_id: int,
    role: str,
    question: str,
    kb_id: int = None,
) -> Generator[str, None, None]:
    """
    SSE 流式问答。

    1. 保存用户消息
    2. 检索知识库
    3. 构建上下文
    4. 调用 LLM 流式生成
    5. 保存 AI 回答与引用
    """
    # 1. 保存用户消息。若最后一条消息是同内容且无回答（上次生成中断），
    #    视为重试，不重复入库，避免同题重复问题堆积。
    last_msg = fetchone(
        "SELECT role, content FROM messages WHERE conversation_id = %s ORDER BY id DESC LIMIT 1",
        (conv_id,)
    )
    if last_msg and last_msg["role"] == "user" and last_msg["content"] == question:
        pass
    else:
        execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'user', %s)",
            (conv_id, question)
        )
    # 首次提问：若会话标题仍为默认「新对话」/空，则用问题首句自动更新标题，
    # 便于在会话列表中区分不同对话（同时兼容历史遗留的默认标题）。
    # 注意：updated_at 必须走 NOW_SQL（SQLite 无 NOW() 函数）。
    new_title = question.strip()[:60] or "新对话"
    execute(
        f"UPDATE conversations SET title = %s, updated_at = {NOW_SQL} "
        "WHERE id = %s AND (title IS NULL OR title = '' OR title = '新对话')",
        (new_title, conv_id),
    )

    # 2. 检索
    hits = retrieve(question, role, user_id, kb_id=kb_id)

    # 3. 构建上下文
    context = build_context(hits)

    # 4. 获取历史对话
    history_rows = fetchall(
        "SELECT role, content FROM messages WHERE conversation_id = %s ORDER BY id DESC LIMIT 6",
        (conv_id,)
    )
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(history_rows)]

    # 发送检索到的引用信息
    citations = []
    for h in hits:
        citations.append({
            "doc_id": h["doc_id"],
            "chunk_index": h["chunk_index"],
            "source_text": _clean_answer_text(h["text"])[:200],
            "title": h.get("filename", ""),
            "similarity": h["similarity"],
        })

    yield f"data: {__import__('json').dumps({'citations': citations}, ensure_ascii=False)}\n\n"

    # 5. 流式生成回答
    full_answer = []
    for chunk in chat_stream(question, context, history):
        yield f"{chunk}\n\n"
        try:
            data = __import__("json").loads(chunk[6:])  # 去掉 "data: " 前缀
            if "content" in data:
                full_answer.append(data["content"])
        except Exception:
            pass

    answer_text = _clean_answer_text("".join(full_answer))

    # 6. 保存 AI 回答
    execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'assistant', %s)",
        (conv_id, answer_text)
    )
    # 获取刚插入的消息 ID
    msg_row = fetchone(
        "SELECT id FROM messages WHERE conversation_id = %s AND role = 'assistant' ORDER BY id DESC LIMIT 1",
        (conv_id,)
    )
    msg_id = msg_row["id"] if msg_row else 0

    # 保存引用
    for c in citations:
        execute(
            "INSERT INTO citations (message_id, document_id, chunk_index, source_text, title, similarity) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (msg_id, c["doc_id"], c["chunk_index"], c["source_text"], c["title"], c["similarity"])
        )


def get_chat_history(user_id: int, limit: int = 50) -> list[dict]:
    """获取用户的全部问答历史（含引用文档）。"""
    rows = fetchall(
        "SELECT m.*, c.user_id, c.title AS conv_title "
        "FROM messages m JOIN conversations c ON m.conversation_id = c.id "
        "WHERE c.user_id = %s ORDER BY m.id DESC LIMIT %s",
        (user_id, limit)
    )
    # 为每条消息关联引用文档
    _attach_citations_batch(rows, order="similarity")
    return rows
