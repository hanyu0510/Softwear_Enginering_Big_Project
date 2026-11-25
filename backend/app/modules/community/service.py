# -*- coding: utf-8 -*-
"""社区模块：首页信息流、帖子详情、评论、点赞、关注。

设计要点（详见《首页信息流设计.md》）：
1. 列表页固定 2 条 SQL：主查询拿帖子 + 作者 + 当前用户的互动态；第二条批量拿图片。
   绝不在循环里查图片 / 查作者 / 查是否点赞（N+1）。
2. 排序是「(点赞 + 2×评论 + 1) / (发布至今小时数 + 2)²」，不是裸的 like_count DESC，
   否则一周前的爆款会永远压在第一条。
3. is_liked / is_favorited / is_following 全部由后端按登录态计算，前端不自己算。
4. 点赞分两种身份：登录用户走幂等 PUT/DELETE（保留红心状态）；游客走纯计数 POST
   （点一次加一次，不记身份、不做去重，按用户选择）。评论必须登录。
"""
from __future__ import annotations

import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping

from app.core.errors import ApiError, bad_request, not_found, unauthorized

SORT_WHITELIST = ("hot", "newest")
SCOPE_WHITELIST = ("all", "following")

MAX_PAGE_SIZE = 100
MAX_TAG_LEN = 20
_TAG_RE = re.compile(r"^[\w\u4e00-\u9fa5·\-]{1,%d}$" % MAX_TAG_LEN)


# --------------------------------------------------------------------------- #
# 入参
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FeedQuery:
    viewer_id: str | None
    page: int
    page_size: int
    tag: str | None
    sort: str
    scope: str
    author_id: str | None = None   # 作者主页：GET /posts?authorId=...

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def _as_int(raw: str | None, field: str, default: int) -> int:
    if raw is None or raw == "":
        return default
    if not str(raw).strip().lstrip("-").isdigit():
        raise bad_request(f"{field} 必须是整数")
    return int(str(raw).strip())


def parse_feed_query(params: Mapping[str, str], viewer_id: str | None) -> FeedQuery:
    """校验并归一化 query 参数。任何不合法都抛 40001，不做「猜一个默认值」。"""
    page = _as_int(params.get("page"), "page", 1)
    if page < 1:
        raise bad_request("page 从 1 开始")

    page_size = _as_int(params.get("pageSize"), "pageSize", 20)
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise bad_request(f"pageSize 取值范围 1~{MAX_PAGE_SIZE}")

    sort = (params.get("sort") or "hot").strip().lower()
    if sort not in SORT_WHITELIST:
        raise bad_request("sort 只能是 hot 或 newest")

    scope = (params.get("scope") or "all").strip().lower()
    if scope not in SCOPE_WHITELIST:
        raise bad_request("scope 只能是 all 或 following")

    tag = (params.get("tag") or "").strip().lstrip("#").strip()
    if tag:
        if not _TAG_RE.match(tag):
            raise bad_request(f"tag 不合法（1~{MAX_TAG_LEN} 个字，不能带空格和符号）")
    else:
        tag = None

    author_id = (params.get("authorId") or "").strip() or None
    if author_id and not re.match(r"^[A-Za-z0-9_-]{1,32}$", author_id):
        raise bad_request("authorId 不合法")

    # 关注流必须有身份：否则「关注了谁」无从判断
    if scope == "following" and not viewer_id:
        raise unauthorized("登录后才能查看关注的人")

    return FeedQuery(viewer_id, page, page_size, tag, sort, scope, author_id)


# --------------------------------------------------------------------------- #
# 查询
# --------------------------------------------------------------------------- #
def _where_clauses(q: FeedQuery) -> tuple[str, dict]:
    """拼 WHERE 片段。所有值都走命名占位符，不拼字符串。"""
    sql = " AND p.status = 'normal'"
    args: dict = {"viewer": q.viewer_id}

    if q.tag:
        sql += " AND EXISTS (SELECT 1 FROM post_tags t WHERE t.post_id = p.id AND t.tag = :tag)"
        args["tag"] = q.tag

    if q.scope == "following":
        sql += (
            " AND EXISTS (SELECT 1 FROM follows fo"
            " WHERE fo.follower_id = :viewer AND fo.followee_id = p.user_id)"
        )
    if q.author_id:
        sql += " AND p.user_id = :author_id"
        args["author_id"] = q.author_id
    return sql, args


def _order_clause(sort: str) -> str:
    """ORDER BY 只能来自白名单，绝不接受外部字符串。"""
    if sort == "newest":
        return "f.created_at DESC, f.id DESC"
    # 热度分已算成 f.hot_score 别名，直接排序；末尾用 id 兜底保证分页稳定
    return "f.hot_score DESC, f.created_at DESC, f.id DESC"


FEED_SQL = """
WITH aged AS (
    SELECT p.id, p.user_id, p.title, p.text, p.post_type, p.outfit_id,
           p.like_count, p.comment_count, p.created_at,
           ((julianday(:now) - julianday(p.created_at)) * 24.0) AS age_hours
    FROM posts p
    WHERE 1 = 1 {where}
),
scored AS (
    -- 热度分：(点赞 + 2×评论 + 1) / (发布至今小时数 + 2)²
    -- 平滑项 1 和 2 的作用：新帖不会因为 0 赞直接沉底，老帖也不会靠历史数据永久霸榜
    SELECT a.*,
           ((a.like_count + a.comment_count * 2.0 + 1.0)
            / ((a.age_hours + 2.0) * (a.age_hours + 2.0))) AS hot_score
    FROM aged a
)
SELECT f.id, f.user_id, f.title, f.text, f.post_type, f.outfit_id, f.like_count, f.comment_count,
       f.created_at, f.age_hours, f.hot_score,
       u.nickname, u.avatar_url,
       EXISTS (SELECT 1 FROM likes l WHERE l.post_id = f.id AND l.user_id = :viewer) AS is_liked,
       EXISTS (SELECT 1 FROM favorites fv
               WHERE fv.target_type = 'post' AND fv.target_id = f.id
                 AND fv.user_id = :viewer) AS is_favorited,
       EXISTS (SELECT 1 FROM follows fo2
               WHERE fo2.follower_id = :viewer AND fo2.followee_id = f.user_id) AS is_following
FROM scored f
JOIN users u ON u.id = f.user_id
ORDER BY {order}
LIMIT :limit OFFSET :offset
"""

COUNT_SQL = "SELECT COUNT(*) AS n FROM posts p WHERE 1 = 1 {where}"


def _now_utc() -> str:
    # SQLite 的 julianday 能正确解析带时区的 ISO 8601
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _chunks(seq: list, size: int = 500) -> Iterable[list]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _load_images(conn: sqlite3.Connection, post_ids: list[str]) -> dict[str, list[dict]]:
    """一次 IN 查询取回本页所有图片，按 post_id 分组。"""
    out: dict[str, list[dict]] = {pid: [] for pid in post_ids}
    if not post_ids:
        return out
    for chunk in _chunks(post_ids):
        marks = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT post_id, url, thumb_url, width, height FROM post_images"
            f" WHERE post_id IN ({marks}) ORDER BY post_id, sort_order",
            chunk,
        ).fetchall()
        for r in rows:
            w, h = int(r["width"]), int(r["height"])
            out[r["post_id"]].append({
                "url": r["url"],
                "thumb_url": r["thumb_url"],
                "width": w,
                "height": h,
                # 前端瀑布流先按这个比例占位，图片没加载完也不会跳版
                "aspect_ratio": round(w / h, 4) if h else 1.0,
            })
    return out


def _load_tags(conn: sqlite3.Connection, post_ids: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {pid: [] for pid in post_ids}
    if not post_ids:
        return out
    for chunk in _chunks(post_ids):
        marks = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT post_id, tag FROM post_tags WHERE post_id IN ({marks})"
            f" ORDER BY post_id, sort_order",
            chunk,
        ).fetchall()
        for r in rows:
            out[r["post_id"]].append(r["tag"])
    return out


def _row_to_item(r: sqlite3.Row, images: list[dict], tags: list[str]) -> dict:
    return {
        "id": r["id"],
        "author": {
            "id": r["user_id"],
            "nickname": r["nickname"],
            "avatar_url": r["avatar_url"],
            # 卡片右下角可以直接显示「已关注」，省一次请求
            "is_following": bool(r["is_following"]),
        },
        # 文档 3.5 的老字段，保留兼容；前端渲染优先用 images
        "image_urls": [img["url"] for img in images],
        "images": images,
        "title": r["title"],
        "text": r["text"],
        "post_type": r["post_type"],
        "tags": tags,
        "outfit_id": r["outfit_id"],
        "like_count": r["like_count"],
        "comment_count": r["comment_count"],
        "is_liked": bool(r["is_liked"]),
        "is_favorited": bool(r["is_favorited"]),
        "created_at": r["created_at"],
        "hot_score": round(r["hot_score"], 4),
    }


def list_feed(conn: sqlite3.Connection, q: FeedQuery) -> dict:
    where, args = _where_clauses(q)
    sql = FEED_SQL.format(where=where, order=_order_clause(q.sort))
    params = dict(args, now=_now_utc(), limit=q.page_size, offset=q.offset)

    rows = conn.execute(sql, params).fetchall()
    post_ids = [r["id"] for r in rows]
    images = _load_images(conn, post_ids)
    tags = _load_tags(conn, post_ids)

    total = conn.execute(COUNT_SQL.format(where=where), args).fetchone()["n"]
    items = [_row_to_item(r, images[r["id"]], tags[r["id"]]) for r in rows]

    return {
        "list": items,
        "total": total,
        "page": q.page,
        "pageSize": q.page_size,
        # 瀑布流必须知道还有没有下一页：靠 len(list) < pageSize 判断，
        # 在 total 变化（别人刚发帖）时会漏掉最后一条
        "hasMore": q.offset + len(items) < total,
        "sort": q.sort,
        "scope": q.scope,
        "tag": q.tag,
        "authorId": q.author_id,
    }


# --------------------------------------------------------------------------- #
# 点赞（P1，但首页卡片要用，先做幂等版本）
# --------------------------------------------------------------------------- #
def set_like(conn: sqlite3.Connection, viewer_id: str | None, post_id: str, liked: bool) -> dict:
    if not viewer_id:
        raise unauthorized("登录后才能点赞")

    post = conn.execute(
        "SELECT id FROM posts WHERE id = ? AND status = 'normal'", (post_id,)
    ).fetchone()
    if post is None:
        raise not_found("帖子不存在或已被删除")

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    try:
        conn.execute("BEGIN IMMEDIATE")
        if liked:
            cur = conn.execute(
                "INSERT OR IGNORE INTO likes (user_id, post_id, created_at) VALUES (?, ?, ?)",
                (viewer_id, post_id, now),
            )
            if cur.rowcount == 1:  # 只有真的新增了才动计数，重复点赞不重复加
                conn.execute("UPDATE posts SET like_count = like_count + 1 WHERE id = ?", (post_id,))
        else:
            cur = conn.execute(
                "DELETE FROM likes WHERE user_id = ? AND post_id = ?", (viewer_id, post_id)
            )
            if cur.rowcount == 1:
                conn.execute(
                    "UPDATE posts SET like_count = MAX(like_count - 1, 0) WHERE id = ?", (post_id,)
                )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    row = conn.execute("SELECT like_count FROM posts WHERE id = ?", (post_id,)).fetchone()
    return {"post_id": post_id, "is_liked": liked, "like_count": row["like_count"]}


# --------------------------------------------------------------------------- #
# 收藏帖子（文档 5.4：PUT/DELETE /posts/:id/bookmark，P1）
# --------------------------------------------------------------------------- #
def set_bookmark(conn: sqlite3.Connection, viewer_id: str | None,
                 post_id: str, bookmarked: bool) -> dict:
    """收藏 / 取消收藏帖子，写 favorites(target_type='post')，幂等。

    边界（文档 3.7 / 5.3.6）：
    - 必须登录——收藏是私人行为，游客不能收藏；
    - 只写 favorites 里 target_type='post' 的记录，账号 /me/favorites 读同一份关系，
      不另建表；单品收藏走 /wish-items，两边不双写；
    - favorites 没有冗余计数（不像 like_count），所以只动关系表。
    """
    if not viewer_id:
        raise unauthorized("登录后才能收藏")

    post = conn.execute(
        "SELECT id FROM posts WHERE id = ? AND status = 'normal'", (post_id,)
    ).fetchone()
    if post is None:
        raise not_found("帖子不存在或已被删除")

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    try:
        conn.execute("BEGIN IMMEDIATE")
        if bookmarked:
            conn.execute(
                "INSERT OR IGNORE INTO favorites"
                " (user_id, target_type, target_id, created_at) VALUES (?, 'post', ?, ?)",
                (viewer_id, post_id, now),
            )
        else:
            conn.execute(
                "DELETE FROM favorites"
                " WHERE user_id = ? AND target_type = 'post' AND target_id = ?",
                (viewer_id, post_id),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return {"post_id": post_id, "is_favorited": bookmarked}


# --------------------------------------------------------------------------- #
# 帖子详情（点卡片进来那一页）
# --------------------------------------------------------------------------- #
def get_post(conn: sqlite3.Connection, post_id: str, viewer: str | None) -> dict:
    row = conn.execute(
        """SELECT p.id, p.user_id, p.title, p.text, p.post_type, p.outfit_id,
                  p.like_count, p.comment_count, p.created_at,
                  u.nickname, u.avatar_url, u.bio,
                  EXISTS (SELECT 1 FROM likes l
                          WHERE l.post_id = p.id AND l.user_id = :viewer) AS is_liked,
                  EXISTS (SELECT 1 FROM favorites fv
                          WHERE fv.target_type = 'post' AND fv.target_id = p.id
                            AND fv.user_id = :viewer) AS is_favorited,
                  EXISTS (SELECT 1 FROM follows fo
                          WHERE fo.follower_id = :viewer AND fo.followee_id = p.user_id) AS is_following
           FROM posts p JOIN users u ON u.id = p.user_id
           WHERE p.id = :pid AND p.status = 'normal'""",
        {"pid": post_id, "viewer": viewer},
    ).fetchone()
    if row is None:
        raise not_found("帖子不存在或已被删除")

    n_posts = conn.execute(
        "SELECT COUNT(*) n FROM posts WHERE user_id = ? AND status = 'normal'", (row["user_id"],)
    ).fetchone()["n"]
    images = _load_images(conn, [post_id])[post_id]
    tags = _load_tags(conn, [post_id])[post_id]

    return {
        "id": row["id"],
        "title": row["title"],
        "text": row["text"],
        "post_type": row["post_type"],
        "author": {
            "id": row["user_id"],
            "nickname": row["nickname"],
            "avatar_url": row["avatar_url"],
            "bio": row["bio"],
            "post_count": n_posts,
            "is_following": bool(row["is_following"]),
        },
        "images": images,
        "image_urls": [img["url"] for img in images],
        "tags": tags,
        "outfit_id": row["outfit_id"],
        "like_count": row["like_count"],
        "comment_count": row["comment_count"],
        "is_liked": bool(row["is_liked"]),
        "is_favorited": bool(row["is_favorited"]),
        "created_at": row["created_at"],
    }


def get_user(conn: sqlite3.Connection, user_id: str, viewer: str | None) -> dict:
    """作者主页资料。帖子列表复用 GET /posts?authorId=...，不在本函数里查。"""
    row = conn.execute(
        """SELECT u.id, u.nickname, u.avatar_url, u.bio,
                  (SELECT COUNT(*) FROM posts p
                   WHERE p.user_id = u.id AND p.status = 'normal') AS post_count,
                  (SELECT COUNT(*) FROM follows f WHERE f.followee_id = u.id) AS follower_count,
                  EXISTS (SELECT 1 FROM follows fo
                          WHERE fo.follower_id = :viewer AND fo.followee_id = u.id) AS is_following
           FROM users u WHERE u.id = :uid""",
        {"uid": user_id, "viewer": viewer},
    ).fetchone()
    if row is None:
        raise not_found("用户不存在")
    return {
        "id": row["id"],
        "nickname": row["nickname"],
        "avatar_url": row["avatar_url"],
        "bio": row["bio"],
        "post_count": row["post_count"],
        "follower_count": row["follower_count"],
        "is_following": bool(row["is_following"]),
    }


# --------------------------------------------------------------------------- #
# 评论
# --------------------------------------------------------------------------- #
COMMENTS_SQL = """
SELECT c.id, c.post_id, c.user_id, c.text, c.parent_id, c.created_at,
       u.nickname, u.avatar_url,
       pc.text AS parent_text, pu.nickname AS parent_nickname
FROM comments c
JOIN users u ON u.id = c.user_id
LEFT JOIN comments pc ON pc.id = c.parent_id
LEFT JOIN users pu ON pu.id = pc.user_id
WHERE c.post_id = :pid
ORDER BY c.created_at ASC, c.id ASC
LIMIT :limit OFFSET :offset
"""


def list_comments(conn: sqlite3.Connection, post_id: str, viewer: str | None,
                  page: int = 1, page_size: int = 20) -> dict:
    if page < 1 or page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise bad_request("page 从 1 开始；pageSize 取值 1~100")
    post = conn.execute(
        "SELECT id FROM posts WHERE id = ? AND status = 'normal'", (post_id,)
    ).fetchone()
    if post is None:
        raise not_found("帖子不存在或已被删除")

    rows = conn.execute(COMMENTS_SQL, {
        "pid": post_id, "limit": page_size, "offset": (page - 1) * page_size,
    }).fetchall()
    total = conn.execute("SELECT COUNT(*) n FROM comments WHERE post_id = ?", (post_id,)).fetchone()["n"]
    items = [{
        "id": r["id"],
        "post_id": r["post_id"],
        "author": {
            "id": r["user_id"],
            "nickname": r["nickname"],
            "avatar_url": r["avatar_url"],
            "is_me": r["user_id"] == viewer,
        },
        "text": r["text"],
        # 回复谁：前端显示「回复 @张三：原文片段」，不用再发一次请求
        "parent_id": r["parent_id"],
        "reply_to": {"nickname": r["parent_nickname"], "text": r["parent_text"]}
        if r["parent_id"] else None,
        "created_at": r["created_at"],
    } for r in rows]
    return {
        "list": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": page * page_size < total,
    }


def add_comment(conn: sqlite3.Connection, viewer: str | None,
                post_id: str, payload: Mapping) -> dict:
    """发表评论 / 回复。必须登录 —— 游客会被 40101 拦在这里。"""
    if not viewer:
        raise unauthorized("登录后才能评论")

    text = str(payload.get("text") or "").strip()
    if not (1 <= len(text) <= 500):
        raise bad_request("评论内容长度 1~500 字")
    parent_id = (payload.get("parent_id") or "").strip() or None

    post = conn.execute(
        "SELECT id, user_id FROM posts WHERE id = ? AND status = 'normal'", (post_id,)
    ).fetchone()
    if post is None:
        raise not_found("帖子不存在或已被删除")
    if parent_id:
        parent = conn.execute(
            "SELECT id FROM comments WHERE id = ? AND post_id = ?", (parent_id, post_id)
        ).fetchone()
        if parent is None:
            raise bad_request("parent_id 不是这条帖子下的评论")

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    cid = "c_" + secrets.token_hex(6)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO comments (id, post_id, user_id, text, parent_id, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (cid, post_id, viewer, text, parent_id, now),
        )
        # 冗余计数同事务维护
        conn.execute("UPDATE posts SET comment_count = comment_count + 1 WHERE id = ?", (post_id,))
        # 写通知：评论别人的帖子才通知，自己评论自己不打扰
        if post["user_id"] != viewer:
            conn.execute(
                "INSERT INTO notifications"
                " (id, user_id, type, from_user_id, target_type, target_id, is_read, created_at)"
                " VALUES (?, ?, 'comment', ?, 'post', ?, 0, ?)",
                (f"n_{cid}", post["user_id"], viewer, post_id, now),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    me = conn.execute(
        "SELECT id, nickname, avatar_url FROM users WHERE id = ?", (viewer,)
    ).fetchone()
    return {
        "id": cid,
        "post_id": post_id,
        "author": {
            "id": me["id"], "nickname": me["nickname"],
            "avatar_url": me["avatar_url"], "is_me": True,
        },
        "text": text,
        "parent_id": parent_id,
        "reply_to": None,
        "created_at": now,
    }


def delete_comment(conn: sqlite3.Connection, viewer: str | None, comment_id: str) -> dict:
    if not viewer:
        raise unauthorized("登录后才能删除评论")
    row = conn.execute(
        "SELECT post_id, user_id FROM comments WHERE id = ?", (comment_id,)
    ).fetchone()
    if row is None:
        raise not_found("评论不存在")
    if row["user_id"] != viewer:
        raise ApiError(40301, "只能删除自己的评论", 403)

    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "DELETE FROM comments WHERE id = ? AND user_id = ?", (comment_id, viewer)
        )
        if cur.rowcount == 1:
            conn.execute(
                "UPDATE posts SET comment_count = MAX(comment_count - 1, 0) WHERE id = ?",
                (row["post_id"],),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"comment_id": comment_id, "deleted": True}


# --------------------------------------------------------------------------- #
# 点赞：登录幂等 / 游客纯计数
# --------------------------------------------------------------------------- #
def like_anonymous(conn: sqlite3.Connection, post_id: str) -> dict:
    """游客点赞：点一次加一次，不记身份、不返回 is_liked（按用户选择的方案）。

    这里没有去重，所以天然可以被刷；这是刻意接受的取舍，写在设计文档里。
    """
    post = conn.execute(
        "SELECT id FROM posts WHERE id = ? AND status = 'normal'", (post_id,)
    ).fetchone()
    if post is None:
        raise not_found("帖子不存在或已被删除")
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE posts SET like_count = like_count + 1 WHERE id = ?", (post_id,))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    count = conn.execute("SELECT like_count FROM posts WHERE id = ?", (post_id,)).fetchone()["like_count"]
    return {"post_id": post_id, "like_count": count, "is_liked": None, "anonymous": True}


# --------------------------------------------------------------------------- #
# 关注（作者主页入口）
# --------------------------------------------------------------------------- #
def toggle_follow(conn: sqlite3.Connection, viewer: str | None,
                  target_id: str, follow: bool) -> dict:
    if not viewer:
        raise unauthorized("登录后才能关注")
    if viewer == target_id:
        raise bad_request("不能关注自己")
    target = conn.execute("SELECT id FROM users WHERE id = ?", (target_id,)).fetchone()
    if target is None:
        raise not_found("用户不存在")

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    # 通知 id 用确定的复合键：同一「我→对方」的关注只对应一条通知。
    # 取消关注时撤回它，关注时用 INSERT OR IGNORE 兜底历史残留，
    # 这样反复「取消 → 再关注」不会因主键冲突报 500。
    notif_id = f"n_follow_{viewer}_{target_id}"
    try:
        conn.execute("BEGIN IMMEDIATE")
        if follow:
            cur = conn.execute("INSERT OR IGNORE INTO follows VALUES (?,?,?)",
                               (viewer, target_id, now))
            added = cur.rowcount == 1
            if added:
                conn.execute(
                    "INSERT OR IGNORE INTO notifications"
                    " (id, user_id, type, from_user_id, target_type, target_id, is_read, created_at)"
                    " VALUES (?, ?, 'follow', ?, 'user', ?, 0, ?)",
                    (notif_id, target_id, viewer, target_id, now),
                )
        else:
            cur = conn.execute("DELETE FROM follows WHERE follower_id = ? AND followee_id = ?",
                               (viewer, target_id))
            added = cur.rowcount == 0  # 本来就没关注
            # 撤回对应的关注通知，否则再关注会因同 id 主键冲突报 500
            conn.execute(
                "DELETE FROM notifications WHERE id = ? AND type = 'follow'",
                (notif_id,),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"user_id": target_id, "is_following": follow}
