"""社区模块：首页信息流（`GET /api/v1/posts`）属于这里。

对外只暴露 `list_feed` / `set_like` / `parse_feed_query`，
框架无关（FastAPI、Flask、stdlib 都能直接调用），便于先本地跑通再挂路由。
"""
