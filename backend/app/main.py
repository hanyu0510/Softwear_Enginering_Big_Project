import json
import logging
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.api import api_router
from app.core import db as shared_db
from app.core import deps as community_deps
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import ROOT, Settings as SharedSettings, get_settings
from app.modules.account.settings import Settings
from app.core.database import Database
from app.core.errors import ApiError, failure
from app.core.rate_limit import RateLimiter
from app.core.security import hash_password
from app.modules.account.integrations import Integrations
from app.modules.account.router import router


def create_app(settings=None, integrations=None, clock=None):
    account_settings = settings if isinstance(settings, Settings) else Settings.from_env()
    shared_settings = settings if isinstance(settings, SharedSettings) else get_settings()
    if isinstance(settings, Settings):
        shared_settings = shared_settings.model_copy(update={
            "database_url": "sqlite:///" + str(settings.database_path),
            "upload_dir": settings.database_path.parent / "uploads"})
    url = make_url(shared_settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise RuntimeError("当前账号与社区适配需要文件型 SQLite DATABASE_URL")
    path = Path(url.database)
    if not path.is_absolute():
        path = ROOT / path
    from dataclasses import replace
    settings = replace(account_settings, database_path=path)
    shared_settings = shared_settings.model_copy(update={"database_url": "sqlite:///" + str(path)})
    app = FastAPI(title="穿搭项目 · 账号后端", version="0.1.0")
    app.state.settings = settings
    app.state.database = Database(settings.database_path)
    shared_settings.upload_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(shared_settings.database_url, connect_args={"check_same_thread": False})
    shared_db.Base.metadata.create_all(engine)
    app.state.orm_engine = engine
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def session_dependency():
        with sessions() as session:
            yield session

    def connection_dependency():
        with app.state.database.connection() as conn:
            yield conn

    app.dependency_overrides[shared_db.get_db] = session_dependency
    app.dependency_overrides[community_deps.get_db] = connection_dependency
    app.dependency_overrides[get_settings] = lambda: shared_settings
    app.state.shared_settings = shared_settings
    app.state.integrations = integrations or Integrations()
    app.state.clock = clock or time.time
    app.state.dummy_password_hash = hash_password("dummy-account-does-not-exist")
    app.state.limiter = RateLimiter()

    @app.exception_handler(ApiError)
    async def api_error(request, exc):
        return failure(request, exc.code, exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        account_paths = ("/api/v1/auth/", "/api/v1/me", "/api/v1/notifications", "/api/v1/dict", "/api/v1/config")
        status = 400 if request.url.path.startswith(account_paths) else 422
        return failure(request,40001,"参数格式不正确，请检查邮箱、字段范围及必填项",status)

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
            logging.getLogger("account").error("Unhandled server error, requestId=%s",request.state.request_id)
            response = failure(request,50001,"服务内部错误，请提供 requestId 排查",500)
        if request.url.path.startswith("/api/v1") and response.headers.get("content-type","").startswith("application/json"):
            raw = (b"".join([chunk async for chunk in response.body_iterator])
                   if hasattr(response,"body_iterator") else response.body)
            payload = json.loads(raw)
            if not isinstance(payload, dict) or not {"code", "message", "data"}.issubset(payload):
                payload = {"code": 0, "message": "ok", "data": payload}
            payload["requestId"] = request.state.request_id
            headers = [(k,v) for k,v in response.raw_headers if k.lower() not in (b"content-length",b"content-type")]
            updated = JSONResponse(payload,status_code=response.status_code)
            updated.raw_headers.extend(headers)
            response = updated
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    app.include_router(api_router)
    app.include_router(router)
    if shared_settings.is_development:
        app.mount("/debug-assets", StaticFiles(directory=ROOT / "app/static/debug"), name="debug-assets")

    @app.get("/health")
    def health(request: Request):
        from app.core.errors import success
        return success(request, {"status": "ok"})

    @app.get("/debug/wardrobe", include_in_schema=False)
    def wardrobe_debug_page(config: SharedSettings = Depends(get_settings)):
        if not config.is_development:
            raise StarletteHTTPException(404)
        return FileResponse(ROOT / "app/static/debug/wardrobe.html")

    @app.get("/", include_in_schema=False)
    def test_page(config: SharedSettings = Depends(get_settings)):
        if not settings.enable_test_page or not config.is_development:
            return JSONResponse({"message":"Account API is running"})
        return FileResponse(ROOT / "account_lab.html")

    @app.get("/account_lab.js", include_in_schema=False)
    def test_script(config: SharedSettings = Depends(get_settings)):
        if not settings.enable_test_page or not config.is_development:
            raise StarletteHTTPException(404)
        return FileResponse(ROOT / "account_lab.js",media_type="text/javascript")

    app.add_middleware(CORSMiddleware,allow_origins=list(settings.allowed_origins),allow_credentials=True,
                       allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],
                       allow_headers=["Authorization","Content-Type","X-Request-Id"],expose_headers=["X-Request-ID"])
    return app


app = create_app()
