"""SQLite 数据访问层。

约定：
- 常规请求使用 flask.g 作用域连接（get_conn），请求结束自动关闭；
- SSE 流式生成器中使用独立连接（new_conn），并自行在 finally 中关闭，
  避免长连接占用请求作用域连接、也避免跨线程共享连接。
"""
import os
import sqlite3

from flask import g

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_schema(cfg) -> None:
    """创建数据目录并执行建表 SQL。"""
    os.makedirs(cfg["DATA_DIR"], exist_ok=True)
    os.makedirs(cfg["UPLOAD_DIR"], exist_ok=True)
    os.makedirs(cfg["CHROMA_DIR"], exist_ok=True)
    with connect(cfg["DATABASE_PATH"]) as conn:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())


def get_conn() -> sqlite3.Connection:
    """请求作用域连接（flask.g 缓存）。"""
    if "db" not in g:
        from flask import current_app

        g.db = connect(current_app.config["DATABASE_PATH"])
    return g.db


def new_conn() -> sqlite3.Connection:
    """独立新连接（供 SSE 生成器使用）。"""
    from flask import current_app

    return connect(current_app.config["DATABASE_PATH"])
