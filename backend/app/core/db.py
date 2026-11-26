# -*- coding: utf-8 -*-
"""全后端共用的 SQLite 数据库入口。

衣橱模块使用 SQLAlchemy Session，社区模块暂时使用 sqlite3 Connection。
两种访问方式默认指向同一个数据库文件，后续由数据库负责人统一迁移。
"""
from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import BACKEND_DIR, get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """SQLAlchemy 会话依赖，供衣橱等 ORM 模块使用。"""
    with SessionLocal() as session:
        yield session


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def _default_sqlite_path() -> Path:
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        return BACKEND_DIR / "data" / "yida.db"
    path = Path(url.database)
    return path if path.is_absolute() else BACKEND_DIR / path


DEFAULT_DB = _default_sqlite_path()
SCHEMA = BACKEND_DIR / "sql" / "schema.sql"


def db_path() -> str:
    """兼容社区演示的 APP_DB，同时默认使用公共 DATABASE_URL。"""
    import os

    return os.environ.get("APP_DB", str(DEFAULT_DB))


def connect(path: str | None = None) -> sqlite3.Connection:
    p = Path(path or db_path())
    p.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None：关掉隐式事务，事务边界自己写，避免 BEGIN 嵌套报错
    conn = sqlite3.connect(str(p), isolation_level=None, check_same_thread=False)
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
    with SCHEMA.open("r", encoding="utf-8") as f:
        conn.executescript(f.read())
