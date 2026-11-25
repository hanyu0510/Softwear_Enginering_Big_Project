# -*- coding: utf-8 -*-
"""公共依赖：可信的当前用户（文档 4.3 第 3 条、5.3.6）。

统一约定：
- Token 只由账号模块验证；其他模块一律通过本文件的 optional_user / require_user
  拿到「可信用户 ID」，绝不自行解析 token，也绝不信前端自填的 userId（文档 4.3）。
- 账号模块接入后，verify_bearer 委托给账号实现；接入前回退到演示 token，
  让本地零依赖服务仍可跑（与 devserver.py 的 dev-me / u_me 保持一致）。
"""
from __future__ import annotations

# 演示回退：账号模块未接入时的本地 token。正式接入后这段不再生效。
_DEMO_TOKEN = "dev-me"
_DEMO_USER_ID = "u_me"


class DemoUser:
    """演示用户对象，接口与账号模块的 User 对齐（至少要有 .id）。"""

    def __init__(self, uid: str):
        self.id = uid


def verify_bearer(authorization: str | None):
    """统一认证入口：账号模块负责验签，返回用户对象或 None。

    接入正式工程时，账号模块实现 ``app.modules.account.deps.verify_bearer``，
    这里优先使用它；未接入时回退到演示 token，社区代码无需改动。
    """
    token = (authorization or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    try:
        from app.modules.account.deps import verify_bearer as account_verify_bearer
    except ImportError:
        # 账号模块尚未接入：演示回退
        return DemoUser(_DEMO_USER_ID) if token == _DEMO_TOKEN else None
    return account_verify_bearer(authorization)


def optional_user(authorization: str | None = None) -> str | None:
    """可选登录：首页游客也能刷；解析失败当未登录，不报错。"""
    user = verify_bearer(authorization)
    return user.id if user else None


def require_user(authorization: str | None = None) -> str:
    """必须登录：发评论、点赞、关注等；未登录抛 40101。"""
    from app.core.errors import unauthorized

    user = verify_bearer(authorization)
    if not user:
        raise unauthorized()
    return user.id
