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
        self.status = status_code
        super().__init__(message)

    def __repr__(self) -> str:
        return f"ApiError(code={self.code}, status={self.status_code}, message={self.message!r})"


def bad_request(message: str) -> ApiError:
    return ApiError(40001, message, 400)


def unauthorized(message: str = "未登录或登录已过期") -> ApiError:
    return ApiError(40101, message, 401)


def not_found(message: str = "资源不存在或不可见") -> ApiError:
    return ApiError(40401, message, 404)


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid4().hex[:12]}")


_UNSET = object()


def success(request=None, data=_UNSET, message="ok") -> dict:
    """兼容公共 success(request, data) 与账号 success(data)。"""
    if isinstance(request, Request):
        rid = request_id(request)
        payload = None if data is _UNSET else data
    else:
        rid = ""
        payload = request if data is _UNSET else data
    return {"code": 0, "message": message, "data": payload, "requestId": rid}


def failure(request, code, message, status):
    return JSONResponse(status_code=status, content={
        "code": code, "message": message, "data": None,
        "requestId": request_id(request),
    })


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return failure(request, exc.code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return failure(request, 40001, "参数格式不正确，请检查邮箱、字段范围及必填项", 422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        code_by_status = {401: 40101, 403: 40301, 404: 40401, 413: 41301, 429: 42901}
        code = code_by_status.get(exc.status_code, 40001 if exc.status_code < 500 else 50001)
        return failure(request, code, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.error("Unhandled server error, requestId=%s", request_id(request))
        return failure(request, 50001, "服务内部错误", 500)
