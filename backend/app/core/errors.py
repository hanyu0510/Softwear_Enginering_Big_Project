# -*- coding: utf-8 -*-
"""统一错误：内部抛 ApiError，适配层负责翻译成文档 4.1 的响应外壳。

业务码与 HTTP 状态的对应关系按 4.2 的约定：40001->400、40101->401、
40401->404、42901->429、50001->500。前端两种都要处理，所以两边都要对。
"""
from __future__ import annotations


class ApiError(Exception):
    def __init__(self, code: int, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def __repr__(self) -> str:  # 便于日志里直接看到业务码
        return f"ApiError(code={self.code}, status={self.status}, message={self.message!r})"


def bad_request(message: str) -> ApiError:
    return ApiError(40001, message, 400)


def unauthorized(message: str = "未登录或登录已过期") -> ApiError:
    return ApiError(40101, message, 401)


def not_found(message: str = "资源不存在或不可见") -> ApiError:
    return ApiError(40401, message, 404)
