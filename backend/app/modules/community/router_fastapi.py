# -*- coding: utf-8 -*-
"""社区模块的 FastAPI 路由（正式工程用）。

本地演示用的是 devserver.py（标准库），两边调的是同一份 service，
所以这里的逻辑改动只需要保证参数名和 5.4 一致，不需要重复实现查询。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, Query

from app.core.deps import get_db
from app.core.errors import unauthorized
from app.modules.community import service

router = APIRouter(tags=["community"])


def optional_viewer(authorization: str | None = Header(default=None)) -> str | None:
    """游客也能刷首页：统一走 core.deps 的可信认证，解析失败当未登录。"""
    from app.core.deps import optional_user

    return optional_user(authorization)


def current_viewer(user_id: str | None = Depends(optional_viewer)) -> str | None:
    return user_id


@router.get("/posts")
def list_posts(
    page: int = Query(1, ge=1, description="从 1 开始"),
    pageSize: int = Query(20, ge=1, le=100),
    tag: str | None = Query(None, max_length=20),
    sort: str = Query("hot", pattern="^(hot|newest)$"),
    scope: str = Query("all", pattern="^(all|following)$"),
    authorId: str | None = Query(None, max_length=32, description="作者主页：只看某人的帖子"),
    viewer: str | None = Depends(current_viewer),
    conn=Depends(get_db),
):
    """首页信息流。响应外层由 main.py 的统一响应处理包装成 {code,message,data,requestId}。"""
    # 这里复用 service 的校验，保证「参数非法 -> 40001」这件事只有一处实现
    q = service.parse_feed_query(
        {"page": page, "pageSize": pageSize, "tag": tag or "", "sort": sort,
         "scope": scope, "authorId": authorId or ""},
        viewer,
    )
    return service.list_feed(conn, q)


@router.get("/posts/{post_id}")
def get_post(post_id: str, viewer: str | None = Depends(current_viewer), conn=Depends(get_db)):
    """帖子详情。"""
    return service.get_post(conn, post_id, viewer)


@router.get("/posts/{post_id}/comments")
def list_comments(
    post_id: str,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    viewer: str | None = Depends(current_viewer),
    conn=Depends(get_db),
):
    return service.list_comments(conn, post_id, viewer, page, pageSize)


@router.post("/posts/{post_id}/comments")
def add_comment(
    post_id: str,
    payload: dict = Body(...),
    viewer: str | None = Depends(current_viewer),
    conn=Depends(get_db),
):
    """发表评论：service 里会检查 viewer，游客返回 40101。"""
    return service.add_comment(conn, viewer, post_id, payload)


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: str, viewer: str | None = Depends(current_viewer), conn=Depends(get_db)):
    return service.delete_comment(conn, viewer, comment_id)


@router.get("/users/{user_id}")
def get_user(user_id: str, viewer: str | None = Depends(current_viewer), conn=Depends(get_db)):
    """作者主页资料；帖子列表复用 GET /posts?authorId=。"""
    return service.get_user(conn, user_id, viewer)


@router.put("/users/{user_id}/follow")
def follow(user_id: str, viewer: str | None = Depends(current_viewer), conn=Depends(get_db)):
    if not viewer:
        raise unauthorized()
    return service.toggle_follow(conn, viewer, user_id, True)


@router.delete("/users/{user_id}/follow")
def unfollow(user_id: str, viewer: str | None = Depends(current_viewer), conn=Depends(get_db)):
    if not viewer:
        raise unauthorized()
    return service.toggle_follow(conn, viewer, user_id, False)


@router.post("/posts/{post_id}/like")
def like_anonymous(post_id: str, conn=Depends(get_db)):
    """游客点赞：纯计数，点一次加一次，不记身份。"""
    return service.like_anonymous(conn, post_id)


@router.put("/posts/{post_id}/like")
def like_post(post_id: str, viewer: str | None = Depends(current_viewer), conn=Depends(get_db)):
    if not viewer:
        raise unauthorized()
    return service.set_like(conn, viewer, post_id, True)


@router.delete("/posts/{post_id}/like")
def unlike_post(post_id: str, viewer: str | None = Depends(current_viewer), conn=Depends(get_db)):
    if not viewer:
        raise unauthorized()
    return service.set_like(conn, viewer, post_id, False)


@router.put("/posts/{post_id}/bookmark")
def bookmark_post(post_id: str, viewer: str | None = Depends(current_viewer), conn=Depends(get_db)):
    """收藏帖子：写 favorites(target_type='post')，需登录，幂等。"""
    if not viewer:
        raise unauthorized()
    return service.set_bookmark(conn, viewer, post_id, True)


@router.delete("/posts/{post_id}/bookmark")
def unbookmark_post(post_id: str, viewer: str | None = Depends(current_viewer), conn=Depends(get_db)):
    if not viewer:
        raise unauthorized()
    return service.set_bookmark(conn, viewer, post_id, False)
