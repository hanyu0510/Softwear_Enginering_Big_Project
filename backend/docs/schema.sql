-- 首版账号SQLite结构；接入团队数据库前需对齐迁移。

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    nickname TEXT NOT NULL,
    avatar_url TEXT,
    password_hash TEXT NOT NULL,
    following_count INTEGER NOT NULL DEFAULT 0 CHECK(following_count >= 0),
    follower_count INTEGER NOT NULL DEFAULT 0 CHECK(follower_count >= 0),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    access_token_hash TEXT NOT NULL UNIQUE,
    access_expires_at REAL NOT NULL,
    refresh_token_hash TEXT NOT NULL UNIQUE,
    refresh_expires_at REAL NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revoked_at REAL
);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_user ON auth_sessions(user_id);
CREATE TABLE IF NOT EXISTS follows (
    follower_id TEXT NOT NULL REFERENCES users(id),
    followee_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY(follower_id, followee_id),
    CHECK(follower_id != followee_id)
);
CREATE INDEX IF NOT EXISTS ix_follows_followee ON follows(followee_id);
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    type TEXT NOT NULL CHECK(type IN ('like','comment','follow')),
    from_user_id TEXT NOT NULL REFERENCES users(id),
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    event_key TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_notifications_owner ON notifications(user_id, created_at);
CREATE TABLE IF NOT EXISTS style_preferences (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    styles TEXT NOT NULL,
    avoid_colors TEXT NOT NULL,
    notes TEXT NOT NULL
);
