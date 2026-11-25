from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, code: int, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status


def success(data=None, message="ok"):
    # requestId 由公共中间件写入，确保所有成功/失败响应都有同一格式。
    return {"code": 0, "message": message, "data": data, "requestId": ""}


def failure(request: Request, code: int, message: str, status: int):
    return JSONResponse(status_code=status, content={
        "code": code, "message": message, "data": None,
        "requestId": getattr(request.state, "request_id", ""),
    })
