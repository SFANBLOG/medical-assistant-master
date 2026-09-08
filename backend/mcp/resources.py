"""
MCP 资源暴露。

将知识库文档暴露为 MCP 资源，支持外部系统读取。
"""
from backend.utils.db import fetchall


def list_knowledge_resources() -> list[dict]:
    """列出所有可访问的知识库文档作为 MCP 资源。

    返回格式：
    [
        {
            "uri": "knowledge://123",
            "name": "文档名.pdf",
            "mimeType": "text/plain",
            "description": "知识库: xxx"
        },
        ...
    ]
    """
    try:
        rows = fetchall(
            "SELECT d.id, d.filename, d.kb_id, k.name AS kb_name "
            "FROM documents d "
            "LEFT JOIN knowledge_bases k ON d.kb_id = k.id "
            "WHERE d.status = 'ready' "
            "ORDER BY d.id DESC LIMIT 100"
        )
    except Exception:
        return []

    return [
        {
            "uri": f"knowledge://{r['id']}",
            "name": r.get("filename", f"文档{r['id']}"),
            "mimeType": "text/plain",
            "description": f"知识库: {r.get('kb_name', '默认')}",
        }
        for r in rows
    ]


def read_knowledge_resource(doc_id: int) -> str:
    """读取指定文档的全部 chunk 内容。

    Args:
        doc_id: 文档 ID

    Returns:
        str: 文档全文（由 chunks 拼接）
    """
    try:
        chunks = fetchall(
            "SELECT text FROM chunks WHERE doc_id = %s ORDER BY chunk_index",
            (doc_id,),
        )
    except Exception:
        return f"读取文档 {doc_id} 失败"

    if not chunks:
        return f"文档 {doc_id} 无内容"

    return "\n\n".join(c["text"] for c in chunks)
