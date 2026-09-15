"""认证与角色（JWT）。"""
import hashlib
import time

import jwt

import config as cfg
from models import db


def hash_password(pwd: str) -> str:
    return hashlib.sha256((pwd + "::salt::medical").encode("utf-8")).hexdigest()


def verify_password(pwd: str, hashed: str) -> bool:
    return hash_password(pwd) == hashed


def create_token(user_id: int, role: str, username: str) -> str:
    payload = {
        "uid": user_id, "role": role, "username": username,
        "exp": int(time.time()) + cfg.JWT_EXPIRE_HOURS * 3600,
    }
    return jwt.encode(payload, cfg.JWT_SECRET, algorithm="HS256")


def decode_token(token: str):
    try:
        return jwt.decode(token, cfg.JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def login(username: str, password: str):
    user = db.query_one("SELECT * FROM users WHERE username=%s", (username,))
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    token = create_token(user["id"], user["role"], user["username"])
    return {
        "token": token,
        "user": {
            "id": user["id"], "username": user["username"],
            "role": user["role"], "display_name": user["display_name"],
        },
    }


def get_user_by_id(uid: int):
    return db.query_one("SELECT * FROM users WHERE id=%s", (uid,))
