# -*- coding: utf-8 -*-
"""数据库连接。正式工程由数据库负责人提供 session 依赖，这里保持同样的使用方式：

    with get_conn() as conn:
        ...
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(BASE_DIR, "data", "app.db")
SCHEMA = os.path.join(BASE_DIR, "sql", "schema.sql")


def db_path() -> str:
    return os.environ.get("APP_DB", DEFAULT_DB)


def connect(path: str | None = None) -> sqlite3.Connection:
    p = path or db_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    # isolation_level=None：关掉隐式事务，事务边界自己写，避免 BEGIN 嵌套报错
    conn = sqlite3.connect(p, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_conn(path: str | None = None):
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    with open(SCHEMA, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
