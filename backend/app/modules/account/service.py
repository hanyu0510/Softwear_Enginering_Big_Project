import json
import math

from app.core.errors import ApiError
from app.core.security import hash_token, iso_time, new_id, new_token

PUBLIC_FIELDS = ("id", "nickname", "avatar_url", "following_count", "follower_count", "created_at")


def user_view(row, private=True):
    fields = (*PUBLIC_FIELDS, "email") if private else PUBLIC_FIELDS
    return {key: row[key] for key in fields}


def find_session(conn, token, now, kind="access"):
    if not token:
        return None
    if kind not in ("access", "refresh"):
        raise ValueError("invalid token kind")
    return conn.execute(
        f"SELECT * FROM auth_sessions WHERE {kind}_token_hash=? AND {kind}_expires_at>? "
        "AND refresh_expires_at>? AND revoked_at IS NULL",
        (hash_token(token), now, now),
    ).fetchone()


def require_identity(conn, token, now):
    session = find_session(conn, token, now)
    if session is None:
        raise ApiError(40101, "未登录或登录凭据已失效", 401)
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    if user is None:
        raise ApiError(40101, "账号不存在", 401)
    return user, session


def issue_session(conn, user_id, now, settings):
    access, refresh = new_token(), new_token()
    cutoff = now + settings.refresh_seconds
    access_expiry = min(now+settings.access_seconds, cutoff)
    conn.execute("""INSERT INTO auth_sessions
        (id,user_id,access_token_hash,access_expires_at,refresh_token_hash,
         refresh_expires_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)""",
        (new_id("sess"), user_id, hash_token(access), access_expiry, hash_token(refresh), cutoff, now, now))
    return access, refresh, cutoff, math.ceil(access_expiry-now)


def revoke_all(conn, user_id, now):
    conn.execute("UPDATE auth_sessions SET revoked_at=?,updated_at=? WHERE user_id=? AND revoked_at IS NULL", (now, now, user_id))


def read_preferences(conn, user_id):
    """推荐模块共用读取函数，不调用内部 HTTP，不另存一份偏好。"""
    row = conn.execute("SELECT * FROM style_preferences WHERE user_id=?", (user_id,)).fetchone()
    return {"styles": json.loads(row["styles"]), "avoid_colors": json.loads(row["avoid_colors"]), "notes": row["notes"]} if row else {"styles": [], "avoid_colors": [], "notes": ""}


def create_notification(conn, *, receiver_id, sender_id, kind, target_type, target_id, event_key, now):
    """社区在自己的业务事务内调用；event_key 标识一次真实事件，重试不重复通知。

    取消后重新点赞是新事件，应传新的event_key；不要只按帖ID去重。
    """
    if receiver_id == sender_id:
        return False
    if kind not in ("like", "comment", "follow"):
        raise ValueError("unsupported notification type")
    cursor = conn.execute("""INSERT INTO notifications
        (id,user_id,type,from_user_id,target_type,target_id,is_read,created_at,event_key)
        VALUES (?,?,?,?,?,?,0,?,?) ON CONFLICT(event_key) DO NOTHING""",
        (new_id("ntf"), receiver_id, kind, sender_id, target_type, target_id, iso_time(now), event_key))
    return bool(cursor.rowcount)
