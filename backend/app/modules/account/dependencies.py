from fastapi import Depends, Request

from app.modules.account.service import require_identity


def get_connection(request: Request):
    with request.app.state.database.connection() as conn:
        yield conn


def access_token(request: Request):
    value = request.headers.get("authorization", "")
    parts = value.split()
    return parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" and len(parts[1]) <= 256 else ""


def current_user(request: Request, conn=Depends(get_connection)):
    """其他模块使用 Depends(current_user) 获取可信用户，不接受客户端 userId。"""
    user, _ = require_identity(conn, access_token(request), request.app.state.clock())
    return user
