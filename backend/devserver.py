# -*- coding: utf-8 -*-
"""零依赖本地联调服务（stdlib http.server）。

正式工程用的是 FastAPI（见 app/main.py、router_fastapi.py）。这里只用标准库，
目的是：不用装任何包就能把 `GET /api/v1/posts` 的真实响应跑出来，供前端联调和原型验证。

    python devserver.py            # http://127.0.0.1:8000/  原型页 + 接口
    python devserver.py --port 8000

演示用的登录态：请求头带 `Authorization: Bearer dev-me` 就是「我」已登录，
不带就是游客。想强制游客态可以在 query 上加 `as=guest`。
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import posixpath
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.db import get_conn, init_db, db_path  # noqa: E402
from app.core.errors import ApiError  # noqa: E402
from app.core.response import fail, new_request_id, ok  # noqa: E402
from app.modules.community import service  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIEW_DIR = os.path.join(ROOT, "preview")
DEV_TOKEN = "dev-me"
DEV_USER = "u_me"


def resolve_viewer(headers, params) -> str | None:
    if (params.get("as") or [""])[0] == "guest":
        return None
    auth = headers.get("Authorization") or ""
    if auth.lower().startswith("bearer ") and auth[7:].strip() == DEV_TOKEN:
        return DEV_USER
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "WardrobeFeed/0.1"
    protocol_version = "HTTP/1.1"

    # ---------------- 基础设施 ----------------
    def log_message(self, fmt, *args):  # 安静一点，只打业务日志
        pass

    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "X-Request-Id")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8",
                   {"X-Request-Id": payload.get("requestId", "")})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---------------- 路由 ----------------
    def do_GET(self):
        self._dispatch("GET")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_POST(self):
        self._dispatch("POST")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            raise ApiError(40001, "请求体必须是 UTF-8 JSON", 400)

    def _dispatch(self, method: str):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        params = parse_qs(parsed.query)
        rid = new_request_id()

        try:
            if path.startswith("/api/"):
                self._api(method, path, params, rid,
                          self._body() if method in ("POST", "PUT") else {})
            elif method == "GET":
                self._static(path)
            else:
                self._json(405, fail(40501, "方法不允许", rid))
        except ApiError as e:
            self._json(e.status, fail(e.code, e.message, rid))
        except BrokenPipeError:
            pass
        except Exception:
            traceback.print_exc()
            self._json(500, fail(50001, "服务内部错误", rid))

    def _api(self, method: str, path: str, params: dict, rid: str, body: dict | None = None):
        viewer = resolve_viewer(self.headers, params)
        body = body or {}
        flat = {k: v[0] for k, v in params.items() if v}
        parts = [p for p in path.split("/") if p]

        # ---------------- 首页信息流 ----------------
        if method == "GET" and path == "/api/v1/posts":
            q = service.parse_feed_query(flat, viewer)
            with get_conn() as conn:
                data = service.list_feed(conn, q)
            self._json(200, ok(data, rid))
            return

        # ---------------- 评论：GET / POST /posts/{id}/comments ----------------
        if (len(parts) == 5 and parts[:3] == ["api", "v1", "posts"]
                and parts[4] == "comments"):
            pid = parts[3]
            with get_conn() as conn:
                if method == "GET":
                    data = service.list_comments(
                        conn, pid, viewer,
                        int(flat.get("page", 1)), int(flat.get("pageSize", 20)),
                    )
                elif method == "POST":
                    data = service.add_comment(conn, viewer, pid, body)
                else:
                    raise ApiError(40501, "方法不允许", 405)
            self._json(200, ok(data, rid))
            return

        # ---------------- 点赞 ----------------
        # POST  = 游客纯计数；PUT/DELETE = 登录用户幂等（有红心状态）
        if (len(parts) == 5 and parts[:3] == ["api", "v1", "posts"]
                and parts[4] == "like"):
            pid = parts[3]
            with get_conn() as conn:
                if method == "POST":
                    data = service.like_anonymous(conn, pid)
                elif method in ("PUT", "DELETE"):
                    data = service.set_like(conn, viewer, pid, method == "PUT")
                else:
                    raise ApiError(40501, "方法不允许", 405)
            self._json(200, ok(data, rid))
            return

        # ---------------- 收藏帖子：PUT/DELETE /posts/{id}/bookmark ----------------
        # 必须登录；写 favorites(target_type='post')，幂等，与单品收藏不双写
        if (len(parts) == 5 and parts[:3] == ["api", "v1", "posts"]
                and parts[4] == "bookmark"):
            if method not in ("PUT", "DELETE"):
                raise ApiError(40501, "方法不允许", 405)
            pid = parts[3]
            with get_conn() as conn:
                data = service.set_bookmark(conn, viewer, pid, method == "PUT")
            self._json(200, ok(data, rid))
            return

        # ---------------- 帖子详情：GET /posts/{id} ----------------
        if len(parts) == 4 and parts[:3] == ["api", "v1", "posts"] and method == "GET":
            with get_conn() as conn:
                data = service.get_post(conn, parts[3], viewer)
            self._json(200, ok(data, rid))
            return

        # ---------------- 删除自己的评论：DELETE /comments/{id} ----------------
        if len(parts) == 4 and parts[2] == "comments" and method == "DELETE":
            with get_conn() as conn:
                data = service.delete_comment(conn, viewer, parts[3])
            self._json(200, ok(data, rid))
            return

        # ---------------- 作者主页资料 + 关注 ----------------
        if len(parts) == 4 and parts[2] == "users" and method == "GET":
            with get_conn() as conn:
                data = service.get_user(conn, parts[3], viewer)
            self._json(200, ok(data, rid))
            return

        if (len(parts) == 5 and parts[2] == "users" and parts[4] == "follow"
                and method in ("PUT", "DELETE")):
            with get_conn() as conn:
                data = service.toggle_follow(conn, viewer, parts[3], method == "PUT")
            self._json(200, ok(data, rid))
            return

        if method == "GET" and path == "/api/v1/healthz":
            with get_conn() as conn:
                n = conn.execute("SELECT COUNT(*) n FROM posts").fetchone()["n"]
            self._json(200, ok({"posts": n, "db": db_path(), "viewer": viewer}, rid))
            return

        raise ApiError(40401, "资源不存在或不可见", 404)

    def _static(self, path: str):
        rel = "index.html" if path in ("/", "") else posixpath.normpath(path).lstrip("/")
        target = os.path.abspath(os.path.join(PREVIEW_DIR, rel))
        if not target.startswith(os.path.abspath(PREVIEW_DIR)) or not os.path.isfile(target):
            self._json(404, fail(40401, "资源不存在", new_request_id()))
            return
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        with open(target, "rb") as f:
            self._send(200, f.read(), ctype)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    with get_conn() as conn:  # 表不存在就先建，避免第一次直接 500
        init_db(conn)

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"feed dev server: http://{args.host}:{args.port}/")
    print(f"  GET /api/v1/posts?sort=hot&page=1&pageSize=8 [--header 'Authorization: Bearer dev-me']")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
