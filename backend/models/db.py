"""数据访问层：默认使用 MySQL（PyMySQL），可用 DB_TYPE=sqlite 回退到本地 SQLite。

约定：
- 运行 backend/app.py 时，若使用 MySQL，会自动创建数据库
  `medical-assistant-master`（DATABASE_NAME）并执行建表 SQL（schema_mysql.sql）；
- 常规请求使用 flask.g 作用域连接（get_conn），请求结束自动关闭；
- SSE 流式生成器中使用独立连接（new_conn），并自行在 finally 中关闭，
  避免长连接占用请求作用域连接、也避免跨线程共享连接。

两种数据库均返回兼容行对象：既支持 row["col"]，也支持 row[0] 与 dict(row)。
"""
import os

import pymysql
import sqlite3

from flask import g

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
MYSQL_SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema_mysql.sql")


class Row(dict):
    """同时支持列名索引、整数索引与 dict(row) 转换的行对象。"""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return dict.__getitem__(self, key)


class MysqlCursor:
    """封装 PyMySQL 游标，返回值统一包装为 Row，并暴露 lastrowid/rowcount。"""

    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        r = self._cur.fetchone()
        return Row(r) if r else None

    def fetchall(self):
        return [Row(r) for r in self._cur.fetchall()]

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def __iter__(self):
        return iter(self.fetchall())


class MysqlConn:
    """PyMySQL 连接封装，对外接口与 sqlite3.Connection 对齐（execute/commit/close/executescript）。"""

    def __init__(self, cfg):
        self._conn = pymysql.connect(
            host=cfg["MYSQL_HOST"],
            port=cfg["MYSQL_PORT"],
            user=cfg["MYSQL_USER"],
            password=cfg["MYSQL_PASSWORD"],
            database=cfg["DATABASE_NAME"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )

    def execute(self, sql, params=None):
        # 代码库统一使用 SQLite 的 ? 占位符，PyMySQL 需要 %s，这里做自动转换
        cur = self._conn.cursor()
        cur.execute(sql.replace("?", "%s"), params or ())
        return MysqlCursor(cur)

    def executescript(self, script):
        for stmt in _split_sql(script):
            if stmt.strip():
                cur = self._conn.cursor()
                cur.execute(stmt)
        self._conn.commit()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
        return False


def _split_sql(script: str) -> list[str]:
    """按分号切分 SQL 脚本（脚本约定：语句内不含分号字符串字面量）。"""
    return [s for s in script.split(";") if s.strip()]


def _ensure_mysql_database(cfg) -> None:
    """以管理员连接创建目标数据库（若不存在）。"""
    admin = pymysql.connect(
        host=cfg["MYSQL_HOST"],
        port=cfg["MYSQL_PORT"],
        user=cfg["MYSQL_USER"],
        password=cfg["MYSQL_PASSWORD"],
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with admin.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{cfg['DATABASE_NAME']}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        admin.close()


def connect(cfg) -> sqlite3.Connection | MysqlConn:
    """按配置创建数据库连接。"""
    if cfg.get("DB_TYPE", "mysql") == "mysql":
        return MysqlConn(cfg)
    db_path = cfg["DATABASE_PATH"]
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_document_visibility(conn) -> None:
    """兼容旧库：为 documents 表补充 visibility 列（公开/私有文档权限）。"""
    if isinstance(conn, MysqlConn):
        rows = conn.execute("SHOW COLUMNS FROM `documents` LIKE 'visibility'").fetchall()
        if not rows:
            conn.execute("ALTER TABLE `documents` ADD COLUMN `visibility` VARCHAR(16) NOT NULL DEFAULT 'public'")
    else:
        cols = conn.execute("PRAGMA table_info(documents)").fetchall()
        if not any(c["name"] == "visibility" for c in cols):
            conn.execute("ALTER TABLE documents ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'")
    conn.commit()


def init_schema(cfg) -> None:
    """创建数据目录（SQLite）并执行建表 SQL。MySQL 自动建库 + 建表。"""
    if cfg.get("DB_TYPE", "mysql") == "mysql":
        _ensure_mysql_database(cfg)
        with connect(cfg) as conn:
            with open(MYSQL_SCHEMA_PATH, encoding="utf-8") as f:
                conn.executescript(f.read())
            _ensure_document_visibility(conn)
        return
    os.makedirs(cfg["DATA_DIR"], exist_ok=True)
    os.makedirs(cfg["UPLOAD_DIR"], exist_ok=True)
    os.makedirs(cfg["CHROMA_DIR"], exist_ok=True)
    with connect(cfg) as conn:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())
        _ensure_document_visibility(conn)


def get_conn() -> sqlite3.Connection | MysqlConn:
    """请求作用域连接（flask.g 缓存）。"""
    if "db" not in g:
        from flask import current_app

        g.db = connect(current_app.config)
    return g.db


def new_conn() -> sqlite3.Connection | MysqlConn:
    """独立新连接（供 SSE 生成器使用）。"""
    from flask import current_app

    return connect(current_app.config)
