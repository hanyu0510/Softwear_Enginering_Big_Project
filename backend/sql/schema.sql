-- 首页信息流 + 帖子详情 / 评论所需表结构（SQLite 演示版）
-- 口径对齐：开发对齐文档 3.1 / 3.5 / 3.6 / 3.7 / 3.8 + 首页设计文档的增补项
-- 正式工程由数据库负责人统一出 Alembic 迁移，这里只做本地联调与验证用。

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id          TEXT PRIMARY KEY,
  nickname    TEXT NOT NULL,
  avatar_url  TEXT,
  bio         TEXT,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
  id            TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL REFERENCES users(id),
  -- 增补：小红书式笔记有「标题 + 正文」两段。title 给列表卡片和详情大标题，
  -- text 是详情正文。保留 text 字段兼容文档 3.5，但语义从「整段文案」收窄为「正文」。
  title         TEXT NOT NULL DEFAULT '',
  text          TEXT NOT NULL DEFAULT '',
  post_type     TEXT NOT NULL DEFAULT 'outfit',  -- 增补：outfit 穿搭推荐 / help 个人求助
  outfit_id     TEXT,                        -- 关联搭配，可空
  like_count    INTEGER NOT NULL DEFAULT 0,  -- 冗余计数，与 likes 同事务维护
  comment_count INTEGER NOT NULL DEFAULT 0,
  status        TEXT NOT NULL DEFAULT 'normal',  -- normal / deleted / hidden
  created_at    TEXT NOT NULL
);

-- 增补：image_urls 是字符串数组，撑不起瀑布流（需要缩略图 + 宽高比）
CREATE TABLE IF NOT EXISTS post_images (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id     TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  url         TEXT NOT NULL,          -- 原图
  thumb_url   TEXT NOT NULL,          -- 列表只加载这张
  width       INTEGER NOT NULL,       -- 原图像素宽
  height      INTEGER NOT NULL,       -- 原图像素高
  sort_order  INTEGER NOT NULL DEFAULT 0
);

-- 增补：话题标签，支撑 ?tag= 筛选与「#话题」展示
-- sort_order 决定展示顺序：第一个标签就是卡片角标上的主标签，不能被字母序打乱
CREATE TABLE IF NOT EXISTS post_tags (
  post_id    TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  tag        TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (post_id, tag)
);

CREATE TABLE IF NOT EXISTS likes (
  user_id    TEXT NOT NULL,
  post_id    TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, post_id)
);

CREATE TABLE IF NOT EXISTS favorites (
  user_id     TEXT NOT NULL,
  target_type TEXT NOT NULL,   -- post / item
  target_id   TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  PRIMARY KEY (user_id, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS follows (
  follower_id TEXT NOT NULL,
  followee_id TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  PRIMARY KEY (follower_id, followee_id)
);

-- 文档 3.6：评论，parent_id 支持「回复某人」
CREATE TABLE IF NOT EXISTS comments (
  id         TEXT PRIMARY KEY,
  post_id    TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  user_id    TEXT NOT NULL REFERENCES users(id),
  text       TEXT NOT NULL,
  parent_id  TEXT,               -- 回复哪条评论；空表示直接评论帖子
  created_at TEXT NOT NULL
);

-- 文档 3.8 / 2.9：type = like | comment | follow
CREATE TABLE IF NOT EXISTS notifications (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id),  -- 接收人
  type        TEXT NOT NULL,
  from_user_id TEXT,
  target_type TEXT,
  target_id   TEXT,
  is_read     INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL
);

-- ---------- 索引：每条都对应一个真实查询 ----------
-- 最新 tab：WHERE status='normal' ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(status, created_at DESC, id DESC);
-- 个人主页 / 关注流按作者取帖
CREATE INDEX IF NOT EXISTS idx_posts_user ON posts(user_id, created_at DESC);
-- 点赞关系反查（我点过哪些、某帖被谁点）
CREATE INDEX IF NOT EXISTS idx_likes_post ON likes(post_id);
-- 帖子收藏反查（target_type 必须一起进索引，否则 item 的收藏会污染）
CREATE INDEX IF NOT EXISTS idx_favorites_target ON favorites(target_type, target_id, user_id);
-- 关注流：我关注了谁（PK 已覆盖 follower_id 前缀），谁关注了我
CREATE INDEX IF NOT EXISTS idx_follows_followee ON follows(followee_id);
-- 批量取图
CREATE INDEX IF NOT EXISTS idx_post_images_post ON post_images(post_id, sort_order);
-- 标签筛选：#通勤 下的帖子
CREATE INDEX IF NOT EXISTS idx_post_tags_tag ON post_tags(tag, post_id);
-- 详情页评论按时间正序
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, created_at, id);
-- 回复列表：查某条评论的所有子回复
CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_id, created_at);
-- 通知：我的未读列表
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read, created_at DESC);
