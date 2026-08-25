"""咨询服务：编排 RAG 检索 -> 大模型流式生成 -> 持久化，输出 SSE。"""
import json
import re
import uuid
from datetime import datetime
from typing import Iterator

from extensions import get_llm
from flask import current_app, Response
from models.db import get_conn
from services.kb_service import (get_kb, can_view_kb, can_view_private_docs,
                                 list_visible_kb_ids, list_known_doc_names)
from services.retriever import retrieve, build_context, build_citations, ChunkHit
from services.cache import cached_json
from utils.errors import ApiError

SYSTEM_PROMPT = """你是一名专业、严谨的医疗健康助手。请仅依据【参考资料】回答用户的问题，不要编造事实。
回答要求：
1. 使用简洁清晰的中文，必要时分点说明；
2. 如果参考资料不足以回答，请如实说明资料未覆盖；
3. 在适当位置用 [1][2] 等编号标注引用来源（编号对应【参考资料】中的序号）。
参考资料如下：
"""

FALLBACK_ANSWER_TMPL = """根据知识库中检索到的以下资料：

{bullets}

说明：当前未配置大模型接口，以下为基于知识库检索的摘要式回答（离线兜底模式），接入真实大模型后可获得更完整的回答。

建议摘要：
{summary}
"""


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _clean_answer(text: str) -> str:
    """移除模型泄漏的内部引用标记、控制字符和重复空白。"""
    text = re.sub(r"\[[0-9]{1,2}\]", "", text or "")
    text = re.sub(r"【(?:参考资料|引用|来源)[^】]*】", "", text)
    text = re.sub(r"(?m)^\s*(?:参考资料|引用来源)\s*:\s*.*$", "", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _synthesize_fallback(question: str, hits) -> str:
    bullets = "\n".join(f"- [{i + 1}] {h.filename}: {h.text[:120]}" for i, h in enumerate(hits))
    summary = "\n".join(f"- [{i + 1}] {h.text}" for i, h in enumerate(hits))
    if not hits:
        summary = "- 知识库中没有检索到相关内容。"
    return FALLBACK_ANSWER_TMPL.format(bullets=bullets or "（无）", summary=summary[:3000])


def _ensure_conversation(user_id: int, conversation_id: str | None, kb_id: int | None, question: str) -> str:
    conn = get_conn()
    if conversation_id:
        row = conn.execute(
            "SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)
        ).fetchone()
        if not row:
            raise ApiError("会话不存在或无权访问", 404)
        return conversation_id
    cid = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO conversations (id, user_id, kb_id, title) VALUES (?,?,?,?)",
        (cid, user_id, kb_id, question[:30]),
    )
    conn.commit()
    return cid


def ask(user: dict, conversation_id: str | None, kb_id: int | None, question: str) -> Response:
    cfg = current_app.config
    if not question or not question.strip():
        raise ApiError("问题不能为空", 400)
    question = question.strip()

    # kb_id=0 或未传 -> 自动检索全部可见知识库（解决「选错知识库答不对」的问题）
    if kb_id in (None, 0):
        kb = {"id": None, "name": "全部知识库（自动匹配）", "visibility": "public", "owner_id": None}
    else:
        kb = get_kb(user, kb_id)  # 校验可见性
        if not can_view_kb(user, kb):
            raise ApiError("无权访问该知识库", 403)

    # 患者/群众/护士：仅检索公开文档；医生/管理员：可检索私有文档
    allow_private = can_view_private_docs(user)
    # 跨知识库检索：当前用户可见的全部知识库（选中的库作为并列时的轻微加权）
    kb_ids = list_visible_kb_ids(user)
    known_names = list_known_doc_names(user)

    # 请求期：建会话、存用户消息、检索
    cid = _ensure_conversation(user["id"], conversation_id, kb["id"], question)
    conn = get_conn()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
        (cid, question),
    )
    conn.commit()

    # 检索结果缓存：相同（问题 + 可见知识库 + 公开/私有权限）直接复用，
    # 避免重复的关键词扫描与向量召回计算；ChunkHit 均为可序列化标量，缓存安全。
    def _retrieve_hits() -> list[dict]:
        hs = retrieve(cfg, kb_ids, question, top_k=cfg["TOP_K"],
                      allow_private=allow_private, bias_kb_id=kb["id"],
                      known_names=known_names)
        return [h.__dict__ for h in hs]

    _cache_key = (
        f"rag:hits:{int(allow_private)}:"
        f"{','.join(map(str, sorted(kb_ids)))}:{question}"
    )
    _hits_dicts = cached_json(_cache_key, cfg["REDIS_TTL"], _retrieve_hits)
    hits = [ChunkHit(**d) for d in _hits_dicts]
    context = build_context(hits)
    citations = build_citations(hits)
    llm = get_llm(cfg)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + context},
        {"role": "user", "content": question},
    ]
    # 生成器在应用上下文之外运行（werkzeug/gunicorn 均为流式迭代），
    # 所有依赖必须在此处捕获，不能在生成器内访问 current_app。
    db_cfg = {
        "DB_TYPE": cfg["DB_TYPE"],
        "DATABASE_PATH": cfg["DATABASE_PATH"],
        "DATABASE_NAME": cfg["DATABASE_NAME"],
        "MYSQL_HOST": cfg["MYSQL_HOST"],
        "MYSQL_PORT": cfg["MYSQL_PORT"],
        "MYSQL_USER": cfg["MYSQL_USER"],
        "MYSQL_PASSWORD": cfg["MYSQL_PASSWORD"],
    }
    from models.db import connect

    def generate() -> Iterator[str]:
        sconn = connect(db_cfg)
        try:
            yield _sse({"type": "meta", "mode": "online" if llm.is_available() else "offline",
                        "kbs": [{"id": kb_id, "name": kb["name"]}]})
            answer = None
            if llm.is_available():
                acc: list[str] = []
                try:
                    for tok in llm.chat_stream(messages):
                        acc.append(tok)
                        yield _sse({"type": "delta", "content": _clean_answer(tok)})
                except Exception:  # noqa: BLE001 在线调用失败（密钥失效/网络异常）降级离线合成
                    pass
                answer = _clean_answer("".join(acc)) or None
            if answer is None:
                answer = _clean_answer(_synthesize_fallback(question, hits))
                for i in range(0, len(answer), 8):  # 模拟流式输出
                    yield _sse({"type": "delta", "content": answer[i : i + 8]})

            cur = sconn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
                (cid, answer),
            )
            message_id = cur.lastrowid
            for c in citations:
                sconn.execute(
                    """INSERT INTO citations (message_id, document_id, chunk_index, source_text, title, similarity)
                       VALUES (?,?,?,?,?,?)""",
                    (message_id, c["document_id"], c["chunk_index"],
                     c["source_text"], c["title"], c["similarity"]),
                )
            sconn.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cid),
            )
            sconn.commit()
            yield _sse({"type": "done", "conversation_id": cid, "message_id": message_id,
                        "citations": citations})
        finally:
            sconn.close()

    resp = Response(generate(), mimetype="text/event-stream")
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Connection"] = "keep-alive"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


def list_conversations(user_id: int, q: str = "", page: int = 1, page_size: int = 10) -> dict:
    conn = get_conn()
    where = "c.user_id = ?"
    params: list = [user_id]
    if q:
        where += " AND c.title LIKE ?"
        params.append(f"%{q}%")
    total = conn.execute(f"SELECT COUNT(*) FROM conversations c WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"""SELECT c.id, c.title, c.created_at, c.updated_at, c.kb_id, k.name AS kb_name,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
            FROM conversations c LEFT JOIN knowledge_bases k ON k.id = c.kb_id
            WHERE {where}
            ORDER BY c.updated_at DESC
            LIMIT ? OFFSET ?""",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return {"total": total, "items": [dict(r) for r in rows]}


def get_conversation(user_id: int, conversation_id: str) -> dict:
    conn = get_conn()
    c = conn.execute(
        "SELECT c.*, k.name AS kb_name FROM conversations c LEFT JOIN knowledge_bases k ON k.id=c.kb_id "
        "WHERE c.id=? AND c.user_id=?",
        (conversation_id, user_id),
    ).fetchone()
    if not c:
        raise ApiError("会话不存在或无权访问", 404)
    msgs = conn.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (conversation_id,)
    ).fetchall()
    items = []
    for m in msgs:
        cit_rows = conn.execute(
            "SELECT document_id, chunk_index, source_text, title, similarity "
            "FROM citations WHERE message_id=? ORDER BY id",
            (m["id"],),
        ).fetchall()
        items.append({**dict(m), "citations": [dict(r) for r in cit_rows]})
    return {"conversation": dict(c), "messages": items}


def delete_conversation(user_id: int, conversation_id: str) -> None:
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)
    )
    conn.commit()
    if cur.rowcount == 0:
        raise ApiError("会话不存在或无权访问", 404)
