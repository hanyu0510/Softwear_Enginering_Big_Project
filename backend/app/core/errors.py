import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, code: int, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid4().hex[:12]}")


def success(request: Request, data=None, message: str = "ok") -> dict:
    return {
        "code": 0,
        "message": message,
        "data": data,
        "requestId": request_id(request),
    }


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": None,
                "requestId": request_id(request),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        details = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in details.get("loc", []) if part != "body")
        message = details.get("msg", "参数无效")
        if location:
            message = f"{location}: {message}"
        return JSONResponse(
            status_code=422,
            content={
                "code": 40001,
                "message": message,
                "data": None,
                "requestId": request_id(request),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        code_by_status = {401: 40101, 403: 40301, 404: 40401, 413: 41301, 429: 42901}
        code = code_by_status.get(exc.status_code, 40001 if exc.status_code < 500 else 50001)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code,
                "message": str(exc.detail),
                "data": None,
                "requestId": request_id(request),
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled server error")
        return JSONResponse(
            status_code=500,
            content={
                "code": 50001,
                "message": "服务内部错误",
                "data": None,
                "requestId": request_id(request),
            },
        )
