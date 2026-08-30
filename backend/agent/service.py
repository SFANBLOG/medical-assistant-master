"""
Agent 问答服务：会话落库 + 运行编排器 + SSE 事件推送 + 轨迹/引用持久化。
"""
import json
from typing import Generator

from backend.utils.db import execute, fetchone, fetchall
from backend.rag.llm import _clean_answer_text
from backend.agent.orchestrator import run_agent


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _get_history(conv_id: str) -> list:
    rows = fetchall(
        "SELECT role, content FROM messages WHERE conversation_id = %s ORDER BY id DESC LIMIT 6",
        (conv_id,),
    )
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def agent_stream_sse(
    conv_id: str,
    user_id: int,
    role: str,
    question: str,
    kb_id=None,
) -> Generator[str, None, None]:
    """
    Agent 模式 SSE 流式问答。

    事件流约定（与编排器一致）：
      thought / tool_call / observation / citations / message / done / error
    """
    # 1. 保存用户消息
    execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'user', %s)",
        (conv_id, question),
    )
    # 首次提问：自动用问题首句更新会话标题
    new_title = question.strip()[:60] or "新对话"
    execute(
        "UPDATE conversations SET title = %s, updated_at = NOW() "
        "WHERE id = %s AND (title IS NULL OR title = '' OR title = '新对话')",
        (new_title, conv_id),
    )

    # 2. 运行 Agent 编排器，收集事件
    steps: list = []
    full_answer: list = []
    citations: list = []

    for event in run_agent(question, role, user_id, kb_id, history=_get_history(conv_id)):
        steps.append(event)

        if event["type"] == "citations":
            citations = event["citations"]
        elif event["type"] == "message":
            full_answer.append(event["content"])

        # 所有事件原样推给前端
        yield _sse(event)

    # 3. 保存 AI 回答 + ReAct 轨迹（可观测）
    answer_text = _clean_answer_text("".join(full_answer))
    execute(
        "INSERT INTO messages (conversation_id, role, content, agent_steps) "
        "VALUES (%s, 'assistant', %s, %s)",
        (conv_id, answer_text, json.dumps(steps, ensure_ascii=False)),
    )
    msg_row = fetchone(
        "SELECT id FROM messages WHERE conversation_id = %s AND role = 'assistant' "
        "ORDER BY id DESC LIMIT 1",
        (conv_id,),
    )
    msg_id = msg_row["id"] if msg_row else 0

    # 4. 保存引用来源
    for c in citations:
        execute(
            "INSERT INTO citations (message_id, document_id, chunk_index, source_text, title, similarity) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (msg_id, c["doc_id"], c["chunk_index"], c["source_text"], c["title"], c["similarity"]),
        )
