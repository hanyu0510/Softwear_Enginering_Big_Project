from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.errors import ApiError


bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request,
) -> str:
    """优先验证账号会话；开发环境保留原有衣橱演示 token。"""
    if credentials is None:
        raise ApiError(40101, "未登录或 token 已过期", 401)

    token = credentials.credentials.strip()
    from app.modules.account.service import require_identity
    with request.app.state.database.connection() as conn:
        try:
            user, _ = require_identity(conn, token, request.app.state.clock())
            return user["id"]
        except ApiError as exc:
            if exc.status != 401:
                raise

    if settings.is_development and token.startswith("dev:"):
        user_id = token.removeprefix("dev:").strip()
        if 1 <= len(user_id) <= 64 and all(ch.isalnum() or ch in "_-" for ch in user_id):
            return user_id
        raise ApiError(40101, "开发 token 中的用户 ID 无效", 401)

    raise ApiError(40101, "未登录或 token 无效", 401)


CurrentUserId = Annotated[str, Depends(get_current_user_id)]
