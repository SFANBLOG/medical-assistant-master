"""
审计日志服务：记录关键操作流水，供合规追溯与人工复核（HITL）联动。

设计原则：
- 审计写入属于「旁路」行为：任何异常都静默吞掉，绝不阻断业务主流程。
- 与人工复核共用一张 audit_logs 表；复核动作（approve/reject）在此留痕。
- 记录要素：操作人、角色、动作、对象类型/ID、摘要、来源 IP、时间。
"""
from backend.utils.db import execute, fetchone, fetchall


def _client_ip() -> str:
    """获取请求来源 IP：读取请求中间件写入的 contextvar（兼容 X-Forwarded-For）。

    非请求上下文（离线脚本 / 后台任务）时 contextvar 取默认空串，与原 Flask 行为一致。
    """
    from backend.utils.request_ctx import client_ip_var
    return client_ip_var.get("")


def write_audit(
    actor_id=None,
    actor_role=None,
    action: str = "",
    target_type: str = None,
    target_id=None,
    detail: str = None,
    ip: str = None,
) -> None:
    """写入一条审计日志。失败静默。"""
    try:
        if ip is None:
            ip = _client_ip()
        execute(
            "INSERT INTO audit_logs (actor_id, actor_role, action, target_type, target_id, detail, ip) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                actor_id,
                actor_role,
                action,
                target_type,
                str(target_id) if target_id is not None else None,
                detail,
                ip,
            ),
        )
    except Exception:  # noqa: BLE001 审计落盘失败不影响业务
        pass


def list_audit(
    action: str = None,
    target_type: str = None,
    actor_id=None,
    page: int = 1,
    size: int = 50,
) -> dict:
    """分页查询审计日志（管理员用）。"""
    where = []
    params = []
    if action:
        where.append("action = %s")
        params.append(action)
    if target_type:
        where.append("target_type = %s")
        params.append(target_type)
    if actor_id is not None:
        where.append("actor_id = %s")
        params.append(actor_id)
    wsql = ("WHERE " + " AND ".join(where)) if where else ""

    total = fetchone(f"SELECT COUNT(*) AS cnt FROM audit_logs {wsql}", tuple(params))["cnt"]
    offset = (page - 1) * size
    rows = fetchall(
        f"SELECT * FROM audit_logs {wsql} ORDER BY id DESC LIMIT %s OFFSET %s",
        tuple(params) + (size, offset),
    )
    return {"total": total, "list": rows, "page": page, "size": size}
