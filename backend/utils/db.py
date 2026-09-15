"""
数据库连接与操作工具。
支持 MySQL 8 和 SQLite 双模式，根据 DB_TYPE 自动切换。
"""
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Optional

from backend.config import DB_TYPE, DATABASE_NAME, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, SQLITE_PATH

# 跨数据库「当前时间」表达式。SQL 里禁止裸写 NOW()：
# MySQL 支持 NOW()，SQLite 没有该函数（会抛 "no such function: NOW"）。
# 统一从这里取，作为字符串拼进 SQL。
NOW_SQL = "NOW()" if DB_TYPE == "mysql" else "datetime('now','localtime')"

try:
    import pymysql
    import pymysql.cursors
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

_lock = threading.Lock()
_db_checked = False  # 是否已确认目标数据库存在（避免每次连接重复 CREATE DATABASE）

def _mysql_connect_retry(**kwargs):
    """带退避重试的 MySQL 连接：容器场景下 MySQL 健康探针通过到真正接受连接之间
    常有一个短暂窗口，首连可能报 Connection refused，重试几次即可，避免启动日志出现
    非致命 traceback。"""
    last_err = None
    for attempt in range(10):
        try:
            return pymysql.connect(**kwargs)
        except pymysql.OperationalError as e:
            last_err = e
            if attempt < 9:
                time.sleep(1.5 * (attempt + 1))
    raise last_err

def _ensure_database():
    """确保目标数据库存在（仅执行一次，后续复用）。"""
    global _db_checked
    if _db_checked:
        return
    admin_conn = _mysql_connect_retry(
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
    return _mysql_connect_retry(
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

        # 对已有数据库做增量迁移（HITL 复核字段）
        _run_hitl_migrations()
    except Exception as e:
        conn.rollback()
        print(f"[DB] Schema 初始化失败: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def _column_exists(table: str, column: str) -> bool:
    """检查表中是否存在指定列。"""
    if DB_TYPE == "mysql":
        try:
            row = fetchone(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
                (table, column),
            )
            return bool(row)
        except Exception:
            return False
    else:
        try:
            rows = fetchall(f"PRAGMA table_info({table})")
            return any(r.get("name") == column for r in rows)
        except Exception:
            return False


def _review_col_types(is_mysql: bool) -> list[tuple[str, str]]:
    """复核字段的 (列名, 列类型)。INT UNSIGNED 是 MySQL 专有，SQLite 用 INTEGER。"""
    id_type = "INT UNSIGNED NULL" if is_mysql else "INTEGER NULL"
    return [
        ("reviewer_id", id_type),
        ("reviewed_at", "DATETIME NULL"),
        ("review_note", "VARCHAR(512) NULL"),
    ]


def _run_hitl_migrations():
    """
    HITL（人工复核）相关字段的增量迁移。

    旧数据库可能没有 review_status / reviewer_id / reviewed_at / review_note 字段，
    这里通过 ALTER TABLE 安全补全，并把历史数据默认标记为 approved，避免检索/复核功能 500。

    注意：ALTER 的列类型里 COMMENT / INT UNSIGNED 是 MySQL 专有语法，SQLite 会直接报
    syntax error，因此按 DB_TYPE 分别生成（见 _review_col_types / _add_col_comment）。
    """
    is_mysql = DB_TYPE == "mysql"

    # ---- documents 表 ----
    if not _column_exists("documents", "review_status"):
        execute(
            "ALTER TABLE documents ADD COLUMN review_status VARCHAR(16) NOT NULL DEFAULT 'approved'"
            + (" COMMENT 'pending/approved/rejected（人工复核）'" if is_mysql else "")
        )
        execute("UPDATE documents SET review_status = 'approved' WHERE review_status IS NULL OR review_status = ''")
        print("[DB] documents.review_status 迁移完成")

    for col, typ in _review_col_types(is_mysql):
        if not _column_exists("documents", col):
            execute(f"ALTER TABLE documents ADD COLUMN {col} {typ}")

    # ---- messages 表 ----
    if not _column_exists("messages", "review_status"):
        execute(
            "ALTER TABLE messages ADD COLUMN review_status VARCHAR(16) NOT NULL DEFAULT 'approved'"
            + (" COMMENT 'pending/approved/rejected（人工复核）'" if is_mysql else "")
        )
        execute("UPDATE messages SET review_status = 'approved' WHERE review_status IS NULL OR review_status = ''")
        print("[DB] messages.review_status 迁移完成")

    for col, typ in _review_col_types(is_mysql):
        if not _column_exists("messages", col):
            execute(f"ALTER TABLE messages ADD COLUMN {col} {typ}")

    # ---- messages 表：Agent ReAct 轨迹（可观测性）----
    if not _column_exists("messages", "agent_steps"):
        # MySQL 用 TEXT（上限 64KB，单条回答的轨迹足够）；SQLite 的 TEXT 亦满足。
        _col_type = "TEXT NULL" if DB_TYPE == "sqlite" else "TEXT NULL COMMENT 'Agent ReAct 轨迹(JSON)'"
        execute(f"ALTER TABLE messages ADD COLUMN agent_steps {_col_type}")
        print("[DB] messages.agent_steps 迁移完成")

    # ---- appointment_requests 表（写操作 HITL：预约请求先复核后建单）----
    _appt_cols = (
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "conversation_id VARCHAR(64) NULL, "
        "user_id INTEGER NOT NULL, "
        "request_json TEXT NOT NULL, "
        "review_status VARCHAR(16) NOT NULL DEFAULT 'pending', "
        "reviewer_id INTEGER NULL, "
        "reviewed_at DATETIME NULL, "
        "review_note VARCHAR(512) NULL, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
    ) if DB_TYPE == "sqlite" else (
        "id INT PRIMARY KEY AUTO_INCREMENT, "
        "conversation_id VARCHAR(64) NULL, "
        "user_id INT NOT NULL, "
        "request_json TEXT NOT NULL, "
        "review_status VARCHAR(16) NOT NULL DEFAULT 'pending', "
        "reviewer_id INT NULL, "
        "reviewed_at DATETIME NULL, "
        "review_note VARCHAR(512) NULL, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
    )
    try:
        execute(f"CREATE TABLE IF NOT EXISTS appointment_requests ({_appt_cols})")
        # 兼容旧表：补 review 相关列
        for _col, _typ in [
            ("reviewer_id", "INTEGER NULL" if DB_TYPE == "sqlite" else "INT NULL"),
            ("reviewed_at", "DATETIME NULL"),
            ("review_note", "VARCHAR(512) NULL"),
        ]:
            if not _column_exists("appointment_requests", _col):
                execute(f"ALTER TABLE appointment_requests ADD COLUMN {_col} {_typ}")
        print("[DB] appointment_requests 迁移完成")
    except Exception as e:  # noqa: BLE001
        print(f"[DB] appointment_requests 迁移跳过：{e}")
