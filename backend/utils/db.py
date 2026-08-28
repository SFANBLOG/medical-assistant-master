"""
数据库连接与操作工具。
支持 MySQL 8 和 SQLite 双模式，根据 DB_TYPE 自动切换。
"""
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Optional

from backend import config
from backend.config import DB_TYPE, DATABASE_NAME, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, SQLITE_PATH

try:
    import pymysql
    import pymysql.cursors
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

_lock = threading.Lock()
_db_checked = False  # 是否已确认目标数据库存在（避免每次连接重复 CREATE DATABASE）

def _ensure_database():
    """确保目标数据库存在（仅执行一次，后续复用）。"""
    global _db_checked
    if _db_checked:
        return
    admin_conn = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        charset="utf8mb4", autocommit=True,
    )
    try:
        with admin_conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DATABASE_NAME}` "
                f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        _db_checked = True
    finally:
        admin_conn.close()


def _get_mysql_conn():
    """获取 MySQL 连接（自动建库）"""
    _ensure_database()

    # 连接目标库
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        database=DATABASE_NAME, charset="utf8mb4",
        autocommit=False, cursorclass=pymysql.cursors.DictCursor,
    )


def _get_sqlite_conn():
    """获取 SQLite 连接"""
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_conn():
    """获取数据库连接（线程安全）"""
    if DB_TYPE == "mysql":
        if not HAS_PYMYSQL:
            raise RuntimeError("PyMySQL 未安装，请 pip install pymysql 或设置 DB_TYPE=sqlite")
        return _get_mysql_conn()
    else:
        return _get_sqlite_conn()


@contextmanager
def db_cursor(commit: bool = True):
    """上下文管理器：自动获取/释放连接与游标。

    用法::

        with db_cursor() as cur:
            cur.execute("SELECT * FROM users")
            rows = cur.fetchall()
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def _placeholder(sql: str) -> str:
    """SQLite 兼容：将 PyMySQL 风格的 %s 占位符转换为 ? 。"""
    if DB_TYPE == "mysql":
        return sql
    return sql.replace("%s", "?")


def execute(sql: str, args: tuple = (), commit: bool = True) -> int:
    """执行单条 SQL，返回受影响行数。"""
    with db_cursor(commit=commit) as cur:
        cur.execute(_placeholder(sql), args)
        return cur.rowcount


def execute_many(sql: str, args_list, commit: bool = True) -> int:
    """批量执行，返回受影响行数。"""
    with db_cursor(commit=commit) as cur:
        cur.executemany(_placeholder(sql), args_list)
        return cur.rowcount


def fetchone(sql: str, args: tuple = ()) -> Optional[dict]:
    """查询单行，返回 dict 或 None。"""
    with db_cursor(commit=False) as cur:
        cur.execute(_placeholder(sql), args)
        row = cur.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        return dict(row)


def fetchall(sql: str, args: tuple = ()) -> list[dict]:
    """查询多行，返回 list[dict]。"""
    with db_cursor(commit=False) as cur:
        cur.execute(_placeholder(sql), args)
        rows = cur.fetchall()
        if rows and isinstance(rows[0], dict):
            return rows
        return [dict(r) for r in rows]


def init_schema():
    """读取并执行建表 SQL（幂等）。"""
    if DB_TYPE == "mysql":
        schema_file = os.path.join(os.path.dirname(__file__), "..", "models", "schema_mysql.sql")
    else:
        schema_file = os.path.join(os.path.dirname(__file__), "..", "models", "schema.sql")

    schema_file = os.path.normpath(schema_file)
    if not os.path.exists(schema_file):
        print(f"[DB] Schema 文件不存在: {schema_file}")
        return

    with open(schema_file, "r", encoding="utf-8") as f:
        sql_text = f.read()

    conn = get_conn()
    cur = conn.cursor()
    try:
        # 去掉注释行后按分号切分执行
        lines = []
        for line in sql_text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("--"):
                lines.append(line)
        clean_sql = "\n".join(lines)

        stmts = [s.strip() for s in clean_sql.split(";") if s.strip()]
        for stmt in stmts:
            cur.execute(stmt)
        conn.commit()
        print(f"[DB] Schema 初始化完成（{DB_TYPE}）")
    except Exception as e:
        conn.rollback()
        print(f"[DB] Schema 初始化失败: {e}")
        raise
    finally:
        cur.close()
        conn.close()
