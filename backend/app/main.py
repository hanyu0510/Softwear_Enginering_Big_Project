import json
import logging
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import ROOT, Settings
from app.core.database import Database
from app.core.errors import ApiError, failure
from app.core.rate_limit import RateLimiter
from app.core.security import hash_password
from app.modules.account.integrations import Integrations
from app.modules.account.router import router


def create_app(settings=None, integrations=None, clock=None):
    settings = settings or Settings.from_env()
    app = FastAPI(title="穿搭项目 · 账号后端", version="0.1.0")
    app.state.settings = settings
    app.state.database = Database(settings.database_path)
    app.state.integrations = integrations or Integrations()
    app.state.clock = clock or time.time
    app.state.dummy_password_hash = hash_password("dummy-account-does-not-exist")
    app.state.limiter = RateLimiter()

    @app.exception_handler(ApiError)
    async def api_error(request, exc):
        return failure(request, exc.code, exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # 不把Pydantic原始input（可能含密码）返回前端。
        return failure(request,40001,"参数格式不正确，请检查邮箱、字段范围及必填项",400)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        code = {404:40401,405:40001}.get(exc.status_code,40001)
        return failure(request,code,"接口不存在" if exc.status_code == 404 else "请求方法或内容不正确",exc.status_code)

    @app.middleware("http")
    async def shared_middleware(request: Request, call_next):
        request.state.request_id = "req_"+uuid.uuid4().hex
        try:
            if request.method not in ("GET","HEAD","OPTIONS"):
                origin = request.headers.get("origin")
                allowed = {str(request.base_url).rstrip("/"), *settings.allowed_origins}
                if origin and origin not in allowed:
                    raise ApiError(40301,"请求来源不允许",403)
            limits = {"/api/v1/auth/login":10,"/api/v1/auth/register":10,"/api/v1/auth/refresh":30,
                      "/api/v1/auth/forgot-password":5,"/api/v1/me/change-password":5}
            if settings.rate_limit_enabled and request.method == "POST" and request.url.path in limits:
                ip = request.client.host if request.client else "unknown"
                app.state.limiter.check((request.url.path,ip),limits[request.url.path])
            response = await call_next(request)
        except ApiError as exc:
            response = failure(request,exc.code,exc.message,exc.status)
        except Exception:
            # 不输出请求体、参数或异常原文，避免日志泄露凭据。
            logging.getLogger("account").error("Unhandled server error, requestId=%s",request.state.request_id)
            response = failure(request,50001,"服务内部错误，请提供 requestId 排查",500)
        if request.url.path.startswith("/api/v1") and response.headers.get("content-type","").startswith("application/json"):
            raw = (b"".join([chunk async for chunk in response.body_iterator])
                   if hasattr(response,"body_iterator") else response.body)
            payload = json.loads(raw)
            payload["requestId"] = request.state.request_id
            headers = [(k,v) for k,v in response.raw_headers if k.lower() not in (b"content-length",b"content-type")]
            updated = JSONResponse(payload,status_code=response.status_code)
            # 保留多个Set-Cookie及其他响应头，不能转换为字典后丢失重复头。
            updated.raw_headers.extend(headers)
            response = updated
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def test_page():
        if not settings.enable_test_page:
            return JSONResponse({"message":"Account API is running"})
        return FileResponse(ROOT / "account_lab.html")

    @app.get("/account_lab.js", include_in_schema=False)
    def test_script():
        if not settings.enable_test_page:
            raise StarletteHTTPException(404)
        return FileResponse(ROOT / "account_lab.js",media_type="text/javascript")

    # CORS最外层保证鉴权/校验错误同样能被允许的前端读取。
    app.add_middleware(CORSMiddleware,allow_origins=list(settings.allowed_origins),allow_credentials=True,
                       allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],
                       allow_headers=["Authorization","Content-Type"],expose_headers=["X-Request-ID"])
    return app
