# -*- coding: utf-8 -*-
"""FastAPI 公共入口（正式工程用）。

统一做三件事，对应文档 4.3 的第 4 条：
1. 所有成功响应包成 {code, message, data, requestId}
2. ApiError / 参数校验错误翻译成 4.2 的业务码（不让 FastAPI 默认的 422 漏出去）
3. requestId 贯穿日志与响应，前端报错时能带回来

本地无依赖演示请跑 devserver.py，不需要这个文件。
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.errors import ApiError
from app.core.response import fail, new_request_id, ok
from app.modules.community.router_fastapi import router as community_router

log = logging.getLogger("app")


def create_app() -> FastAPI:
    app = FastAPI(title="穿搭推荐 · 后端", version="0.1.0")

    # 开发期只放行明确的前端 Origin，不用通配（文档 4.4 第 6 条）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    app.include_router(community_router)

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or new_request_id()
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response

    @app.exception_handler(ApiError)
    async def on_api_error(request: Request, exc: ApiError):
        rid = getattr(request.state, "request_id", None)
        return JSONResponse(fail(exc.code, exc.message, rid), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", None)
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", [])[1:]) or "参数"
        msg = f"{loc} 不合法"
        return JSONResponse(fail(40001, msg, rid), status_code=400)

    return app


app = create_app()
