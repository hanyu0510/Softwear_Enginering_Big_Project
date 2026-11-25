import json
import math
import sqlite3

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.database import transaction
from app.core.errors import ApiError, success
from app.core.security import hash_password, hash_token, iso_time, new_id, new_token, verify_password
from app.modules.account.dependencies import access_token, current_user, get_connection
from app.modules.account.dictionaries import STYLES, dictionary_data
from app.modules.account.schemas import ChangePasswordBody, ForgotBody, LoginBody, PreferencesBody, ProfilePatch, RegisterBody
from app.modules.account.service import create_notification, find_session, issue_session, read_preferences, require_identity, revoke_all, user_view

router = APIRouter(prefix="/api/v1", tags=["账号"])
COOKIE = "refresh_token"
COOKIE_PATH = "/api/v1/auth"
Page = Query(default=1, ge=1)
PageSize = Query(default=20, ge=1, le=100)


def write_cookie(response, value, cutoff, request):
    response.set_cookie(COOKIE, value, max_age=max(0, math.floor(cutoff-request.app.state.clock())),
                        path=COOKIE_PATH, httponly=True, secure=request.app.state.settings.cookie_secure, samesite="lax")


def clear_cookie(response, request):
    response.delete_cookie(COOKIE, path=COOKIE_PATH, httponly=True,
                           secure=request.app.state.settings.cookie_secure, samesite="lax")


def require_write_user(conn, request):
    # 在写事务内重新校验，避免另一请求撤销会话后仍修改资料。
    return require_identity(conn, access_token(request), request.app.state.clock())[0]


@router.post("/auth/register")
def register(body: RegisterBody, request: Request, conn=Depends(get_connection)):
    digest = hash_password(body.password)
    try:
        with transaction(conn):
            conn.execute("INSERT INTO users (id,email,nickname,password_hash,created_at) VALUES (?,?,?,?,?)",
                         (new_id("u"), body.email, body.nickname, digest, iso_time(request.app.state.clock())))
    except sqlite3.IntegrityError:
        raise ApiError(40901, "邮箱已被注册", 409)
    # 不建立会话、不设置 Cookie，也不返回 token。
    return success(message="注册成功，请登录")


@router.post("/auth/login")
def login(body: LoginBody, request: Request, response: Response, conn=Depends(get_connection)):
    user = conn.execute("SELECT * FROM users WHERE email=?", (body.email,)).fetchone()
    encoded = user["password_hash"] if user else request.app.state.dummy_password_hash
    if not verify_password(body.password, encoded) or user is None:
        raise ApiError(40101, "邮箱或密码错误", 401)
    with transaction(conn):
        # 密码验证后再次比较版本，避免并发改密码后签发基于旧密码的新会话。
        fresh = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        if fresh["password_hash"] != encoded or fresh["email"] != body.email:
            raise ApiError(40101, "账号信息已变化，请重新登录", 401)
        token, refresh, cutoff, expires = issue_session(conn, user["id"], request.app.state.clock(), request.app.state.settings)
    write_cookie(response, refresh, cutoff, request)
    return success({"token": token, "expiresIn": expires, "user": user_view(fresh)})


@router.post("/auth/refresh")
def refresh(request: Request, response: Response, conn=Depends(get_connection)):
    now = request.app.state.clock()
    with transaction(conn):
        old = find_session(conn, request.cookies.get(COOKIE, ""), now, "refresh")
        if old is None:
            raise ApiError(40101, "刷新凭据已失效，请重新登录", 401)
        token, refresh_token = new_token(), new_token()
        expiry = min(now+request.app.state.settings.access_seconds, old["refresh_expires_at"])
        cursor = conn.execute("""UPDATE auth_sessions SET access_token_hash=?,access_expires_at=?,
            refresh_token_hash=?,updated_at=? WHERE id=? AND refresh_token_hash=? AND revoked_at IS NULL""",
            (hash_token(token), expiry, hash_token(refresh_token), now, old["id"], old["refresh_token_hash"]))
        if cursor.rowcount != 1:
            raise ApiError(40101, "刷新凭据已被使用，请重新登录", 401)
    write_cookie(response, refresh_token, old["refresh_expires_at"], request)
    return success({"token": token, "expiresIn": math.ceil(expiry-now)})


@router.post("/auth/logout")
def logout(request: Request, response: Response, conn=Depends(get_connection)):
    now = request.app.state.clock()
    with transaction(conn):
        a = find_session(conn, access_token(request), now)
        r = find_session(conn, request.cookies.get(COOKIE, ""), now, "refresh")
        if a is not None and r is not None and a["id"] != r["id"]:
            raise ApiError(40001, "登录凭据不属于同一会话")
        selected = a if a is not None else r
        if selected:
            conn.execute("UPDATE auth_sessions SET revoked_at=?,updated_at=? WHERE id=?", (now, now, selected["id"]))
    clear_cookie(response, request)
    return success(message="已退出登录")


@router.post("/auth/forgot-password")
def forgot_password(body: ForgotBody, request: Request, response: Response, conn=Depends(get_connection)):
    # 按用户确认的课程约定直接重置，不加入邮件/恢复码流程。
    digest = hash_password(body.newPassword)
    now = request.app.state.clock()
    clear = False
    with transaction(conn):
        user = conn.execute("SELECT * FROM users WHERE email=?", (body.email,)).fetchone()
        if user is None:
            raise ApiError(40401, "未找到账号", 404)
        cookie_session = find_session(conn, request.cookies.get(COOKIE, ""), now, "refresh")
        clear = cookie_session is not None and cookie_session["user_id"] == user["id"]
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (digest, user["id"]))
        revoke_all(conn, user["id"], now)
    if clear:
        clear_cookie(response, request)
    return success(message="密码重置成功，请登录")


@router.get("/me")
def me(user=Depends(current_user)):
    return success(user_view(user))


@router.patch("/me")
def patch_me(body: ProfilePatch, request: Request, conn=Depends(get_connection), user=Depends(current_user)):
    fields = body.model_dump(exclude_unset=True)
    if any(value is None for value in fields.values()):
        raise ApiError(40001, "资料字段不能传 null；未修改的字段请省略")
    try:
        with transaction(conn):
            user = require_write_user(conn, request)
            updates = {}
            if "nickname" in fields:
                updates["nickname"] = fields["nickname"]
            if "email" in fields:
                updates["email"] = fields["email"]
            if "avatarFileId" in fields:
                updates["avatar_url"] = request.app.state.integrations.uploads.resolve_avatar(
                    conn, user_id=user["id"], file_id=fields["avatarFileId"])
            if updates:
                assignment = ",".join(f"{name}=?" for name in updates)
                conn.execute(f"UPDATE users SET {assignment} WHERE id=?", (*updates.values(), user["id"]))
            updated = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
    except sqlite3.IntegrityError:
        raise ApiError(40901, "邮箱已被其他账号使用", 409)
    return success(user_view(updated))


@router.post("/me/change-password")
def change_password(body: ChangePasswordBody, request: Request, response: Response,
                    conn=Depends(get_connection), user=Depends(current_user)):
    encoded = user["password_hash"]
    if not verify_password(body.oldPassword, encoded):
        raise ApiError(40001, "原密码错误")
    digest = hash_password(body.newPassword)
    with transaction(conn):
        user = require_write_user(conn, request)
        if user["password_hash"] != encoded:
            raise ApiError(40001, "密码已变化，请重新验证")
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (digest, user["id"]))
        revoke_all(conn, user["id"], request.app.state.clock())
    clear_cookie(response, request)
    return success(message="密码修改成功，请重新登录")


@router.get("/users/{user_id}")
def public_user(user_id: str, conn=Depends(get_connection)):
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if row is None:
        raise ApiError(40401, "用户不存在", 404)
    return success(user_view(row, private=False))


@router.get("/me/posts")
@router.get("/me/likes")
@router.get("/me/favorites")
def my_posts(request: Request, page: int = Page, pageSize: int = PageSize,
             conn=Depends(get_connection), user=Depends(current_user)):
    kind = request.url.path.rsplit("/", 1)[-1]
    result = request.app.state.integrations.community.list_posts(
        conn, user_id=user["id"], kind=kind, page=page, page_size=pageSize)
    return success(result)


@router.post("/users/{user_id}/follow")
@router.delete("/users/{user_id}/follow")
def follow(user_id: str, request: Request, conn=Depends(get_connection), user=Depends(current_user)):
    with transaction(conn):
        user = require_write_user(conn, request)
        if user_id == user["id"]:
            raise ApiError(40001, "不能关注自己")
        if conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone() is None:
            raise ApiError(40401, "用户不存在", 404)
        if request.method == "POST":
            event_id = new_id("follow")
            changed = conn.execute("INSERT OR IGNORE INTO follows VALUES (?,?,?)", (user["id"], user_id, iso_time(request.app.state.clock()))).rowcount
            if changed:
                conn.execute("UPDATE users SET following_count=following_count+1 WHERE id=?", (user["id"],))
                conn.execute("UPDATE users SET follower_count=follower_count+1 WHERE id=?", (user_id,))
                create_notification(conn, receiver_id=user_id, sender_id=user["id"], kind="follow",
                                    target_type="user", target_id=user["id"], event_key=event_id, now=request.app.state.clock())
        else:
            changed = conn.execute("DELETE FROM follows WHERE follower_id=? AND followee_id=?", (user["id"], user_id)).rowcount
            if changed:
                conn.execute("UPDATE users SET following_count=following_count-1 WHERE id=?", (user["id"],))
                conn.execute("UPDATE users SET follower_count=follower_count-1 WHERE id=?", (user_id,))
    return success(message="已关注" if request.method == "POST" else "已取消关注")


@router.get("/me/following")
@router.get("/me/followers")
def follow_list(request: Request, page: int = Page, pageSize: int = PageSize,
                conn=Depends(get_connection), user=Depends(current_user)):
    following = request.url.path.endswith("/following")
    owner, target = ("follower_id", "followee_id") if following else ("followee_id", "follower_id")
    # 读事务使计数和列表处于同一个快照，避免并发变动造成分页不一致。
    conn.execute("BEGIN")
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM follows WHERE {owner}=?", (user["id"],)).fetchone()[0]
        rows = conn.execute(f"SELECT u.* FROM follows f JOIN users u ON u.id=f.{target} "
                            f"WHERE f.{owner}=? ORDER BY f.created_at DESC,u.id DESC LIMIT ? OFFSET ?",
                            (user["id"], pageSize, (page-1)*pageSize)).fetchall()
        output = []
        for row in rows:
            data = user_view(row, private=False)
            data["is_following"] = conn.execute("SELECT 1 FROM follows WHERE follower_id=? AND followee_id=?", (user["id"],row["id"])).fetchone() is not None
            output.append(data)
    finally:
        conn.rollback()
    return success({"list": output, "total": total, "page": page, "pageSize": pageSize})


@router.get("/notifications")
def notifications(request: Request, page: int = Page, pageSize: int = PageSize,
                  conn=Depends(get_connection), user=Depends(current_user)):
    conn.execute("BEGIN")
    try:
        total = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id=?", (user["id"],)).fetchone()[0]
        rows = conn.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", (user["id"],pageSize,(page-1)*pageSize)).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data.pop("event_key")
            data["is_read"] = bool(data["is_read"])
            sender = conn.execute("SELECT * FROM users WHERE id=?", (row["from_user_id"],)).fetchone()
            data["from_user"] = user_view(sender, private=False)
            result.append(data)
    finally:
        conn.rollback()
    return success({"list": result, "total": total, "page": page, "pageSize": pageSize})


@router.put("/notifications/{notification_id}/read")
def mark_read(notification_id: str, request: Request, conn=Depends(get_connection), user=Depends(current_user)):
    with transaction(conn):
        user = require_write_user(conn, request)
        cursor = conn.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notification_id,user["id"]))
        if not cursor.rowcount:
            raise ApiError(40401, "通知不存在或不可见", 404)
    return success(message="已标记为已读")


@router.get("/me/style-preferences")
def preferences(conn=Depends(get_connection), user=Depends(current_user)):
    return success(read_preferences(conn,user["id"]))


@router.put("/me/style-preferences")
def save_preferences(body: PreferencesBody, request: Request, conn=Depends(get_connection), user=Depends(current_user)):
    if any(value not in STYLES for value in body.styles):
        raise ApiError(40001, "风格不在统一字典中")
    color_names = request.app.state.settings.color_names
    if body.avoid_colors and not color_names:
        raise ApiError(40001, "颜色白名单尚未由衣橱和推荐提供，当前可先保存空的避开颜色")
    if any(value not in color_names for value in body.avoid_colors):
        raise ApiError(40001, "颜色不在统一白名单中")
    values = {"styles": list(dict.fromkeys(body.styles)), "avoid_colors": list(dict.fromkeys(body.avoid_colors)), "notes": body.notes}
    with transaction(conn):
        user = require_write_user(conn, request)
        conn.execute("INSERT INTO style_preferences VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET styles=excluded.styles,avoid_colors=excluded.avoid_colors,notes=excluded.notes",
                     (user["id"],json.dumps(values["styles"]),json.dumps(values["avoid_colors"]),values["notes"]))
    return success(values)


@router.get("/dict")
def dictionaries(request: Request, user=Depends(current_user)):
    return success(dictionary_data(request.app.state.settings.color_names))


@router.get("/config")
def frontend_config(request: Request, user=Depends(current_user)):
    from app.modules.account.integrations import CommunityNotConnected, UploadsNotConnected
    return success({
        "accountEnabled": True,
        "myPostListsEnabled": not isinstance(request.app.state.integrations.community,CommunityNotConnected),
        "avatarUpdateEnabled": not isinstance(request.app.state.integrations.uploads,UploadsNotConnected),
        "colorPreferencesEnabled": bool(request.app.state.settings.color_names),
    })
