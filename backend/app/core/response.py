# -*- coding: utf-8 -*-
"""统一响应外壳（文档 4.1）：{code, message, data, requestId}。"""
from __future__ import annotations

import secrets


def new_request_id() -> str:
    return "req_" + secrets.token_hex(4)


def ok(data=None, request_id: str | None = None) -> dict:
    return {
        "code": 0,
        "message": "ok",
        "data": data,
        "requestId": request_id or new_request_id(),
    }


def fail(code: int, message: str, request_id: str | None = None) -> dict:
    return {
        "code": code,
        "message": message,
        "data": None,
        "requestId": request_id or new_request_id(),
    }
