# 团队工程接入说明

## 1. 一个应用、一个数据库

本包create_app是本机运行入口；迁入团队已有FastAPI时，导入account.router并注册到现有应用，不要另起服务器。
账号路由prefix已经包含/api/v1，注册时不要再次叠加同样前缀。
将Settings、Database、异常响应、CORS/Origin检查合并到团队公共层；如果已有SQLAlchemy/Alembic，按现有模型和事务接口迁移本包SQL，不能并排保留另一套users和会话数据库。
docs/schema.sql展示本包的实际账号字段；notifications.event_key用于业务事件重试去重，是需要和数据库同学确认的新物理字段。
这里只交付SQLite运行适配；不是在不知道团队数据库时擅自决定最终数据库。

## 2. 可信当前用户

```python
from fastapi import Depends
from app.modules.account.dependencies import current_user

@router.get('/example')
def example(user=Depends(current_user)):
    user_id = user['id']
    # 所有本人资源查询使用这个ID，不接受前端自填userId替代。
```

此依赖使用同一请求的公共数据库连接，校验access token的哈希、有效期和会话撤销状态。
业务写入如果需要与登录失效原子协调，应在同一写事务内重新校验；参考PATCH /me。

## 3. 社区帖子列表

运行应用默认CommunityNotConnected返回明确错误。社区提供一个实现list_posts的对象：

```python
class CommunityAdapter:
    def list_posts(self, conn, *, user_id, kind, page, page_size):
        # 使用团队真实查询，kind只能为posts/likes/favorites。
        # posts=本人发布；likes=本人点赞；favorites=本人收藏的帖子。
        # 过滤已删除、不可见资源，total按可见记录统计；稳定倒序分页。
        # 每条卡片字段与5.4信息流一致；不把心愿单品混进favorites。
        return community_service.query_my_posts(conn, user_id, kind, page, page_size)
```

示例中的community_service是交接占位名称，不存在于本包；请替换为社区实际方法，不是可直接运行的社区实现。
返回结构必须是 {list:[帖子卡片...], total:整数, page:整数, pageSize:整数}。
账号只提供三条列表入口，不实现帖子发布、点赞/收藏写入或第二套社区数据表。

## 4. 头像文件查询

```python
class UploadsAdapter:
    def resolve_avatar(self, conn, *, user_id, file_id):
        # 从已有上传记录查找文件；检查存在、未删除、属于user_id、类型为允许的图片。
        # 返回能供公开头像展示的URL；不能暴露私人衣物原图的可猜地址。
        return upload_service.resolve_owned_avatar_url(conn, user_id, file_id)
```

upload_service同样需要替换成上传模块的真实方法。文件不存在或不可归本人使用时抛ApiError(40401,...,404)，类型不合规抛ApiError(40001,...)，查询服务故障不能伪装为保存成功。
头像解析发生在资料写事务内；适配器不要自行提交账号事务。若媒体处理耗时，先在上传阶段完成缩略/公开头像转换，这里只做关联查询。

本机工厂注入方式：

```python
from app.main import create_app
from app.modules.account.integrations import Integrations

# 准备好实际的两个Adapter之后再注入。
app = create_app(integrations=Integrations(community=CommunityAdapter(), uploads=UploadsAdapter()))
```

## 5. 社区创建通知

```python
from app.modules.account.service import create_notification

# 在真实点赞/评论写入成功的同一业务事务中调用：
create_notification(
    conn,
    receiver_id=post_author_id,
    sender_id=current_user_id,
    kind='like',
    target_type='post',
    target_id=post_id,
    event_key=actual_like_event_id,
    now=now_timestamp,
)
```

只在关系真实新增时调用；event_key对应一次事件，失败重试复用它。取消后重新点赞是新事件，不应永远按“用户＋帖子”去重通知。
函数不自行提交事务，不给自己发通知，相同event_key不会重复写入。
通知目标被删后的跳转由前端调用目标详情时显示不可用，账号模块不冒充社区判断目标是否存在。

## 6. 推荐读取偏好

```python
from app.modules.account.service import read_preferences
preferences = read_preferences(conn, user_id)
```

没有设置时固定返回styles=[]、avoid_colors=[]、notes=''。推荐负责人决定如何应用这些约束，不在账号侧另写推荐逻辑。

## 7. 环境与文档同步

- 账号固定采用随机access/refresh，不是JWT；前端不要尝试解码token。
- 登录/刷新/退出/修改密码响应包含或清除Cookie，跨域前端必须credentials:include。
- 正式前端使用原文档的JSON外层和错误码；schema中的额外字段拒绝，不能靠传userId修改别人的资料。
- /dict默认没有颜色白名单；衣橱/推荐确认后统一配置ACCOUNT_COLOR_NAMES，当前不是账号自定颜色集合。
- /config目前返回accountEnabled、myPostListsEnabled、avatarUpdateEnabled、colorPreferencesEnabled四项。它们是本轮实现的配置键，应告知前端统一采用。
- /me/liked-posts和/me/bookmarked-posts未注册；社区若决定保留别名，直接接三条列表相同方法，不能另写查询。
- 日志不应记录请求密码、Authorization或原始refresh Cookie；requestId用于排查。
