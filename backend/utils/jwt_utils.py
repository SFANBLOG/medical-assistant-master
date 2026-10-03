"""
JWT 认证工具：签发/验证 token，并以 FastAPI 依赖形式提供登录态与角色门控。

迁移说明：原 Flask 版用 @login_required / @role_required 装饰器把 payload 写入 g，
现改为依赖注入——端点通过 `user: dict = Depends(get_current_user)` 直接拿到已校验的
payload；角色受限用 `Depends(require_roles("admin", ...))`。鉴权失败抛 HTTPException，
由 backend.utils.errors 的统一处理器归一成 {"error": ...} 响应。
"""
import datetime

import jwt

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.config import JWT_SECRET, JWT_EXP_HOURS


def create_token(user_id: int, username: str, role: str) -> str:
    """签发 JWT。"""
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXP_HOURS),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """解码 JWT，失败返回 None。"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# auto_error=False：缺失/非 Bearer 头时返回 None，交由下方依赖统一产出中文错误
_security = HTTPBearer(auto_error=False)


def _extract_payload(creds: HTTPAuthorizationCredentials | None) -> dict:
    """从 Bearer 凭据解析并校验 payload，失败抛 401。"""
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="认证令牌无效或已过期")
    return payload


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(_security)) -> dict:
    """依赖：要求登录，返回 payload（含 user_id / username / role）。"""
    return _extract_payload(creds)


def require_roles(*roles):
    """依赖工厂：要求登录且角色在白名单内，否则 403。"""
    def _dep(creds: HTTPAuthorizationCredentials | None = Depends(_security)) -> dict:
        payload = _extract_payload(creds)
        if payload.get("role") not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return payload
    return _dep
