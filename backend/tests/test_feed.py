# -*- coding: utf-8 -*-
"""首页信息流的接口测试。

    python -m unittest discover -s tests -v      # 在 backend/ 目录下执行
    python tests/test_feed.py

覆盖：排序、筛选、关注流、分页、参数校验、互动状态、点赞幂等、HTTP 层响应外壳。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

# 必须在导入 app.* 之前指定测试库，避免污染 data/app.db
_TMP = tempfile.mkdtemp(prefix="feedtest_")
os.environ["APP_DB"] = os.path.join(_TMP, "test.db")

import seed  # noqa: E402
from app.core.db import get_conn  # noqa: E402
from app.core.errors import ApiError  # noqa: E402
from app.modules.community import service  # noqa: E402

VIEWER = seed.VIEWER


def setUpModule():
    seed.main(keep=False)


def feed(**params):
    viewer = params.pop("viewer", None)
    with get_conn() as conn:
        q = service.parse_feed_query({k: str(v) for k, v in params.items()}, viewer)
        return service.list_feed(conn, q)


class FeedQueryTest(unittest.TestCase):
    def test_default_hot_returns_envelope_fields(self):
        data = feed(viewer=VIEWER)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["pageSize"], 20)
        self.assertEqual(data["total"], 14)
        self.assertTrue(data["hasMore"] is False)
        self.assertEqual(len(data["list"]), 14)

    def test_hot_score_is_monotonic(self):
        scores = [p["hot_score"] for p in feed(viewer=VIEWER)["list"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_hot_prefers_fresh_over_old_high_like(self):
        """post_11 点赞最多但已 96 小时，不应排第一；post_2（8 小时/342 赞）应在前。"""
        ids = [p["id"] for p in feed(viewer=VIEWER)["list"]]
        self.assertLess(ids.index("post_2"), ids.index("post_11"))

    def test_newest_is_desc(self):
        items = feed(viewer=VIEWER, sort="newest")["list"]
        times = [i["created_at"] for i in items]
        self.assertEqual(times, sorted(times, reverse=True))

    def test_tag_filter(self):
        data = feed(viewer=VIEWER, tag="通勤")
        self.assertGreater(data["total"], 0)
        for item in data["list"]:
            self.assertIn("通勤", item["tags"])

    def test_tag_accepts_hash_prefix(self):
        self.assertEqual(feed(viewer=VIEWER, tag="#通勤")["total"], feed(viewer=VIEWER, tag="通勤")["total"])

    def test_unknown_tag_is_empty_not_error(self):
        data = feed(viewer=VIEWER, tag="不存在的标签")
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["list"], [])

    def test_pagination_no_overlap(self):
        p1 = feed(viewer=VIEWER, pageSize=5, page=1)["list"]
        p2 = feed(viewer=VIEWER, pageSize=5, page=2)["list"]
        p3 = feed(viewer=VIEWER, pageSize=5, page=3)
        self.assertEqual(len(p3["list"]), 4)
        self.assertFalse(p3["hasMore"])
        self.assertFalse({i["id"] for i in p1} & {i["id"] for i in p2})

    def test_pagination_page_size_bounds(self):
        self.assertEqual(len(feed(viewer=VIEWER, pageSize=2)["list"]), 2)
        with self.assertRaises(ApiError) as ctx:
            feed(viewer=VIEWER, pageSize=101)
        self.assertEqual(ctx.exception.code, 40001)

    def test_invalid_params(self):
        for bad in ({"page": 0}, {"page": "abc"}, {"pageSize": 0}, {"sort": "popular"}, {"scope": "friends"}):
            with self.assertRaises(ApiError, msg=str(bad)) as ctx:
                feed(viewer=VIEWER, **bad)
            self.assertEqual(ctx.exception.code, 40001)

    def test_tag_too_long(self):
        with self.assertRaises(ApiError) as ctx:
            feed(viewer=VIEWER, tag="啊" * 21)
        self.assertEqual(ctx.exception.code, 40001)


class FollowingScopeTest(unittest.TestCase):
    def test_guest_cannot_use_following(self):
        with self.assertRaises(ApiError) as ctx:
            feed(scope="following")
        self.assertEqual(ctx.exception.code, 40101)
        self.assertEqual(ctx.exception.status, 401)

    def test_following_only_returns_followed_authors(self):
        data = feed(viewer=VIEWER, scope="following")
        authors = {i["author"]["id"] for i in data["list"]}
        self.assertTrue(authors.issubset(set(seed.FOLLOWS)))
        self.assertTrue(authors)


class ViewerStateTest(unittest.TestCase):
    def test_guest_has_no_interaction_state(self):
        for item in feed(sort="newest")["list"]:
            self.assertFalse(item["is_liked"])
            self.assertFalse(item["is_favorited"])
            self.assertFalse(item["author"]["is_following"])

    def test_logged_in_state_matches_tables(self):
        items = {i["id"]: i for i in feed(viewer=VIEWER, sort="newest")["list"]}
        self.assertTrue(items["post_2"]["is_liked"])
        self.assertTrue(items["post_6"]["is_liked"])
        self.assertFalse(items["post_1"]["is_liked"])
        self.assertTrue(items["post_4"]["is_favorited"])
        self.assertTrue(items["post_1"]["author"]["is_following"])

    def test_images_carry_ratio_for_masonry(self):
        for item in feed(viewer=VIEWER)["list"]:
            self.assertTrue(item["images"])
            img = item["images"][0]
            self.assertAlmostEqual(img["aspect_ratio"], round(img["width"] / img["height"], 4))
            self.assertEqual(item["image_urls"][0], img["url"])


class LikeTest(unittest.TestCase):
    def test_like_is_idempotent(self):
        with get_conn() as conn:
            base = conn.execute("SELECT like_count FROM posts WHERE id='post_3'").fetchone()["like_count"]
            first = service.set_like(conn, VIEWER, "post_3", True)
            second = service.set_like(conn, VIEWER, "post_3", True)
            self.assertEqual(first["like_count"], base + 1)
            self.assertEqual(second["like_count"], base + 1)

            back1 = service.set_like(conn, VIEWER, "post_3", False)
            back2 = service.set_like(conn, VIEWER, "post_3", False)
            self.assertEqual(back1["like_count"], base)
            self.assertEqual(back2["like_count"], base)

    def test_like_requires_login(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.set_like(conn, None, "post_3", True)
        self.assertEqual(ctx.exception.code, 40101)

    def test_like_missing_post(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.set_like(conn, VIEWER, "post_nope", True)
        self.assertEqual(ctx.exception.code, 40401)


class HttpLayerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import devserver

        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), devserver.Handler)
        cls.port = cls.srv.server_address[1]
        cls.t = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def get(self, path, token=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_ok_envelope(self):
        status, body = self.get("/api/v1/posts?sort=hot&pageSize=8")
        self.assertEqual(status, 200)
        self.assertEqual(body["code"], 0)
        self.assertIsNone(body.get("error"))
        self.assertTrue(body["requestId"].startswith("req_"))
        self.assertEqual(len(body["data"]["list"]), 8)
        self.assertTrue(body["data"]["hasMore"])

    def test_guest_following_returns_401(self):
        status, body = self.get("/api/v1/posts?scope=following")
        self.assertEqual(status, 401)
        self.assertEqual(body["code"], 40101)
        self.assertIsNone(body["data"])

    def test_logged_in_following(self):
        status, body = self.get("/api/v1/posts?scope=following", token="dev-me")
        self.assertEqual(status, 200)
        self.assertTrue(body["data"]["list"])

    def test_bad_param_returns_400(self):
        status, body = self.get("/api/v1/posts?pageSize=999")
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], 40001)

    def test_like_endpoint(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/v1/posts/post_5/like", method="PUT"
        )
        req.add_header("Authorization", "Bearer dev-me")
        with urllib.request.urlopen(req) as r:
            body = json.loads(r.read().decode("utf-8"))
        self.assertEqual(body["code"], 0)
        self.assertTrue(body["data"]["is_liked"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class DetailTest(unittest.TestCase):
    def test_detail_has_title_type_body_and_author(self):
        with get_conn() as conn:
            p = service.get_post(conn, "post_1", VIEWER)
            p2 = service.get_post(conn, "post_2", VIEWER)
        self.assertIn("不摆拍", p["title"])
        self.assertEqual(p["post_type"], "outfit")
        self.assertEqual(p2["post_type"], "help")
        self.assertIn("先说身材", p["text"])
        self.assertEqual(p["author"]["nickname"], "阿岚的衣橱")
        self.assertTrue(p["author"]["post_count"] >= 1)
        self.assertEqual(p["tags"][0], "梨形穿搭")
        self.assertEqual(p["images"][0]["aspect_ratio"], 0.75)

    def test_detail_state_follows_viewer(self):
        with get_conn() as conn:
            logged = service.get_post(conn, "post_1", VIEWER)
            guest = service.get_post(conn, "post_1", None)
        self.assertTrue(logged["author"]["is_following"])
        self.assertFalse(guest["author"]["is_following"])
        self.assertFalse(guest["is_liked"])

    def test_missing_post_is_404(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.get_post(conn, "post_nope", VIEWER)
        self.assertEqual(ctx.exception.code, 40401)

    def test_author_page_filters_by_author(self):
        data = feed(viewer=VIEWER, authorId="u_1")
        self.assertTrue(data["list"])
        self.assertEqual({i["author"]["id"] for i in data["list"]}, {"u_1"})
        self.assertTrue(data["authorId"] == "u_1")

    def test_author_profile(self):
        with get_conn() as conn:
            u = service.get_user(conn, "u_1", VIEWER)
        self.assertEqual(u["nickname"], "阿岚的衣橱")
        self.assertTrue(u["is_following"])
        self.assertTrue(u["post_count"] >= 2)


class CommentTest(unittest.TestCase):
    def test_comment_list_has_reply_info(self):
        with get_conn() as conn:
            data = service.list_comments(conn, "post_1", VIEWER)
        self.assertEqual(data["total"], 4)
        reply = [c for c in data["list"] if c["parent_id"]][0]
        self.assertEqual(reply["reply_to"]["nickname"], "MOMO酱")
        self.assertTrue(reply["reply_to"]["text"])
        self.assertTrue(any(c["author"]["is_me"] for c in data["list"]))

    def test_comment_requires_login(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.add_comment(conn, None, "post_1", {"text": "游客来评论"})
        self.assertEqual(ctx.exception.code, 40101)

    def test_comment_bad_text(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.add_comment(conn, VIEWER, "post_1", {"text": "  "})
        self.assertEqual(ctx.exception.code, 40001)

    def test_add_comment_updates_count_and_notification(self):
        with get_conn() as conn:
            base = conn.execute("SELECT comment_count FROM posts WHERE id='post_3'").fetchone()["comment_count"]
            note_before = conn.execute(
                "SELECT COUNT(*) n FROM notifications WHERE user_id='u_3' AND type='comment'"
            ).fetchone()["n"]
            c = service.add_comment(conn, VIEWER, "post_3", {"text": "这篇对我很有用！"})
            after = conn.execute("SELECT comment_count FROM posts WHERE id='post_3'").fetchone()["comment_count"]
            note_after = conn.execute(
                "SELECT COUNT(*) n FROM notifications WHERE user_id='u_3' AND type='comment'"
            ).fetchone()["n"]
        self.assertEqual(after, base + 1)
        self.assertEqual(note_after, note_before + 1)
        self.assertEqual(c["author"]["id"], VIEWER)
        self.assertFalse(c["author"]["is_me"] is False)

    def test_reply_validates_parent(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.add_comment(conn, VIEWER, "post_1", {"text": "回复", "parent_id": "c_5"})
        self.assertEqual(ctx.exception.code, 40001)  # c_5 属于 post_2

    def test_delete_only_own_comment(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.delete_comment(conn, VIEWER, "c_1")  # u_2 的评论
        self.assertEqual(ctx.exception.code, 40301)


class AnonymousLikeTest(unittest.TestCase):
    def test_anonymous_like_counts_every_click(self):
        with get_conn() as conn:
            base = conn.execute("SELECT like_count FROM posts WHERE id='post_8'").fetchone()["like_count"]
            a = service.like_anonymous(conn, "post_8")
            b = service.like_anonymous(conn, "post_8")
        self.assertEqual(a["like_count"], base + 1)
        self.assertEqual(b["like_count"], base + 2)
        self.assertTrue(a["anonymous"])
        self.assertIsNone(a["is_liked"])

    def test_anonymous_like_missing_post(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.like_anonymous(conn, "post_nope")
        self.assertEqual(ctx.exception.code, 40401)


class FollowTest(unittest.TestCase):
    def test_follow_is_idempotent(self):
        with get_conn() as conn:
            first = service.toggle_follow(conn, VIEWER, "u_5", True)
            second = service.toggle_follow(conn, VIEWER, "u_5", True)
            self.assertTrue(first["is_following"])
            self.assertTrue(second["is_following"])
            back = service.toggle_follow(conn, VIEWER, "u_5", False)
            self.assertFalse(back["is_following"])

    def test_refollow_after_unfollow_is_idempotent(self):
        """取消关注后再次关注不应报 500（通知 id 冲突回归）。"""
        with get_conn() as conn:
            # u_6 初始未被关注；走完整的 关注→取消→再关注 循环
            self.assertTrue(service.toggle_follow(conn, VIEWER, "u_6", True)["is_following"])
            self.assertFalse(service.toggle_follow(conn, VIEWER, "u_6", False)["is_following"])
            # 再关注：修复前这里会因 n_follow_u_me_u_6 通知已存在而报错
            again = service.toggle_follow(conn, VIEWER, "u_6", True)
            self.assertTrue(again["is_following"])
            # 同一对关注关系只有一条通知，不重复堆积
            n = conn.execute(
                "SELECT COUNT(*) n FROM notifications"
                " WHERE type='follow' AND from_user_id=? AND target_id=?",
                (VIEWER, "u_6"),
            ).fetchone()["n"]
            self.assertEqual(n, 1)
            # 再取消一次，通知也应被撤回
            service.toggle_follow(conn, VIEWER, "u_6", False)
            n2 = conn.execute(
                "SELECT COUNT(*) n FROM notifications"
                " WHERE type='follow' AND from_user_id=? AND target_id=?",
                (VIEWER, "u_6"),
            ).fetchone()["n"]
            self.assertEqual(n2, 0)

    def test_cannot_follow_self(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.toggle_follow(conn, VIEWER, VIEWER, True)
        self.assertEqual(ctx.exception.code, 40001)


class BookmarkTest(unittest.TestCase):
    """收藏帖子（文档 5.4 PUT/DELETE /posts/:id/bookmark）。"""

    def test_bookmark_requires_login(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.set_bookmark(conn, None, "post_2", True)
        self.assertEqual(ctx.exception.code, 40101)

    def test_bookmark_is_idempotent_and_readable(self):
        # post_9 初始未被 u_me 收藏；走完整 收藏→重复→取消→再收藏
        with get_conn() as conn:
            before = conn.execute(
                "SELECT COUNT(*) n FROM favorites"
                " WHERE user_id=? AND target_type='post' AND target_id='post_9'", (VIEWER,)
            ).fetchone()["n"]
            self.assertEqual(before, 0)

            first = service.set_bookmark(conn, VIEWER, "post_9", True)
            self.assertTrue(first["is_favorited"])
            service.set_bookmark(conn, VIEWER, "post_9", True)  # 重复不应报错
            n = conn.execute(
                "SELECT COUNT(*) n FROM favorites"
                " WHERE user_id=? AND target_type='post' AND target_id='post_9'", (VIEWER,)
            ).fetchone()["n"]
            self.assertEqual(n, 1)  # 幂等：只有一条

            # 列表/详情的 is_favorited 必须读到这份关系
            detail = service.get_post(conn, "post_9", VIEWER)
            self.assertTrue(detail["is_favorited"])

            back = service.set_bookmark(conn, VIEWER, "post_9", False)
            self.assertFalse(back["is_favorited"])
            n2 = conn.execute(
                "SELECT COUNT(*) n FROM favorites"
                " WHERE user_id=? AND target_type='post' AND target_id='post_9'", (VIEWER,)
            ).fetchone()["n"]
            self.assertEqual(n2, 0)

    def test_bookmark_missing_post_is_404(self):
        with get_conn() as conn:
            with self.assertRaises(ApiError) as ctx:
                service.set_bookmark(conn, VIEWER, "post_nope", True)
        self.assertEqual(ctx.exception.code, 40401)

    def test_bookmark_does_not_touch_item_favorites(self):
        """帖子收藏不能污染单品收藏（文档 3.7：两边不双写）。"""
        with get_conn() as conn:
            service.set_bookmark(conn, VIEWER, "post_3", True)
            rows = conn.execute(
                "SELECT target_type FROM favorites WHERE user_id=? AND target_id='post_3'", (VIEWER,)
            ).fetchall()
        self.assertTrue(all(r["target_type"] == "post" for r in rows))


class HttpExtraTest(unittest.TestCase):
    """详情页 / 评论 / 匿名点赞 / 关注的 HTTP 路由。"""

    @classmethod
    def setUpClass(cls):
        import devserver

        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), devserver.Handler)
        cls.port = cls.srv.server_address[1]
        cls.t = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def req(self, method, path, body=None, token=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method)
        if data is not None:
            r.add_header("Content-Type", "application/json")
        if token:
            r.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_detail_route(self):
        status, body = self.req("GET", "/api/v1/posts/post_1")
        self.assertEqual(status, 200)
        self.assertEqual(body["code"], 0)
        self.assertIn("不摆拍", body["data"]["title"])
        self.assertEqual(body["data"]["post_type"], "outfit")

    def test_comments_route(self):
        status, body = self.req("GET", "/api/v1/posts/post_1/comments")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["total"], 4)

    def test_guest_comment_is_401(self):
        status, body = self.req("POST", "/api/v1/posts/post_1/comments", {"text": "游客评论"})
        self.assertEqual(status, 401)
        self.assertEqual(body["code"], 40101)

    def test_logged_comment_is_200(self):
        status, body = self.req("POST", "/api/v1/posts/post_1/comments",
                                {"text": "登录后的评论"}, token="dev-me")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["author"]["id"], seed.VIEWER)

    def test_anonymous_like_route(self):
        status, body = self.req("POST", "/api/v1/posts/post_8/like")
        self.assertEqual(status, 200)
        self.assertTrue(body["data"]["anonymous"])
        self.assertIsNone(body["data"]["is_liked"])

    def test_guest_bookmark_is_401(self):
        status, body = self.req("PUT", "/api/v1/posts/post_2/bookmark")
        self.assertEqual(status, 401)
        self.assertEqual(body["code"], 40101)

    def test_logged_bookmark_route(self):
        status, body = self.req("PUT", "/api/v1/posts/post_5/bookmark", token="dev-me")
        self.assertEqual(status, 200)
        self.assertTrue(body["data"]["is_favorited"])
        status, body = self.req("DELETE", "/api/v1/posts/post_5/bookmark", token="dev-me")
        self.assertEqual(status, 200)
        self.assertFalse(body["data"]["is_favorited"])

    def test_user_profile_and_follow_route(self):
        status, body = self.req("GET", "/api/v1/users/u_1")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["nickname"], "阿岚的衣橱")
        status, body = self.req("PUT", "/api/v1/users/u_6/follow", token="dev-me")
        self.assertEqual(status, 200)
        self.assertTrue(body["data"]["is_following"])
