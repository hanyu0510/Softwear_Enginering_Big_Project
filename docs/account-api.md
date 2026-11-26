# 账号模块接口约定与接入状态

对应登录注册与“我的”后端。对外前缀/api/v1。未接入项和待确认项保留原标记，不改其他模块既有接口。

### 0.4 账号代码与接口对照补充（本轮）

本轮基于 `account_backend_v1` 核对，仅补充账号实现细节和必要交接，不新增业务接口、不改变其他模块正文。

| 状态 | 内容 | 使用方式 |
|---|---|---|
| 已确认的业务契约 | 5.3 的 22 个方法/路径、请求字段、认证与刷新、注册不自动登录、邮箱直接修改、原密码修改密码、收藏仅帖子 | 作为账号实现与前端对接依据 |
| 已实现、待前端同步确认 | 字段长度/数组上限、`/config` 的四个键、通知响应附带的 `from_user` | 本轮明确列出；队友确认后成为共同契约，未确认前不能假设前端已采用 |
| 已有本地实现、待数据库/社区确认 | `notifications.event_key`、通知创建内部方法及跨模块数据库连接适配 | 属于交接提案，不因为本地代码已有就认定全组批准 |
| 尚未接入 | 我的帖子/点赞/收藏真实查询、头像文件真实查询、共同颜色白名单 | 保留接口，不能宣称已完成实际业务联调 |

SQLite 和 Python sqlite3 是本地运行适配，不改变 4.3 中数据库/ORM仍待全组确认的状态。本轮不强行要求队友换数据库或增加表字段；不同意某个实现细节时，应调整对应代码并同步本文，而不是只改文档掩盖差异。接口检查通过不等于跨模块验收完成。


### 4.4 账号登录、自动刷新与前端认证约定

1. **注册与登录分离。** 注册成功仅创建账号，返回 `code=0`、`data=null`；不创建会话、不设置 refresh Cookie。前端提示后跳登录页，可预填邮箱，密码框为空。登录成功才签发登录凭据。
2. **两种随机凭据。** access token 和 refresh token 均由后端使用安全随机生成器产生，至少具备 256 位随机性；它们是不透明字符串，不要求采用 JWT。会话表只存哈希，其他模块共用账号提供的当前用户依赖，不自行解析 token。
3. **有效期。** access token 最长 2 小时，refresh token 从本次登录起固定 7 天；不使用滑动续期。接近第 7 天时，新 access token 的有效期不得超过会话截止时间，`expiresIn` 返回实际剩余秒数（通常为 7200）。允许多设备登录，会话相互独立。
4. **前端存储。** access token 放在 `sessionStorage`，业务请求自动带 Bearer Header；不提供“记住我”。refresh token 仅由后端放入 HttpOnly Cookie，前端不读取、不把它放入 JSON 或本地存储。关闭标签页后 access token 不再保留；若 refresh Cookie 尚有效，重新打开页面时可以通过刷新恢复登录状态，这是自动刷新方案的预期行为。
5. **Cookie 约定。** 名称 `refresh_token`，Path 为 `/api/v1/auth`，不设置 Domain；本机同站开发采用 `HttpOnly; SameSite=Lax`，HTTPS 部署另加 `Secure`。Cookie 过期时间不晚于固定的会话截止时间，轮换时不重置为新的 7 天。清除 Cookie 时使用相同名称与 Path。
6. **跨域联调。** 前端 API 请求统一启用凭据携带（Fetch 的 `credentials: "include"` 或 Axios 的 `withCredentials: true`）；后端允许明确的前端 Origin 和凭据，不能用通配 Origin。开发时统一使用 localhost 或统一使用 127.0.0.1，不混用。优先同站不同端口或同源代理；若以后真正跨站部署，需要另行调整 Cookie/CSRF 方案，不直接照搬本机配置。Cookie 参与的登录、刷新、退出写操作校验允许的 Origin。
7. **刷新流程。** 业务请求收到 `40101`，前端共享同一个进行中的刷新请求；成功后保存新 access token，原请求最多重试一次。刷新返回 `40101` 才清除登录状态并跳登录页；登录/注册/忘记密码不进入刷新拦截，刷新接口不能触发自身刷新，重试后的请求不能再次刷新。网络故障或服务内部错误只提示并结束本次重试，不伪装成凭据失效、不无限循环。
8. **启动恢复。** 页面启动时发现 `sessionStorage` 中没有 access token，可尝试一次刷新；成功则恢复用户资料，凭据无效则显示未登录页面。refresh token 过期或撤销后必须重新输入邮箱和密码登录。
9. **刷新轮换。** 每次成功刷新原子替换本会话的两种 token 哈希，旧 access token 和旧 refresh token 均失效，刷新期限保持原值。前端应防止并发刷新；已轮换凭据再次请求返回 `40101`，不得再签发有效凭据。
10. **失效范围。** 退出只撤销当前会话；登录后修改密码或忘记密码重置成功，撤销该用户全部 access/refresh 会话。修改邮箱不改变用户 ID，不撤销当前或其他有效会话；后续登录只认新邮箱。


### 5.3 账号功能（后端）

本节负责登录注册（版面一）和“我的”账号管理（版面五）的后端。路径均省略公共前缀 `/api/v1`；响应统一使用 4.1 的外层结构。登录和刷新机制以 4.4 为准，社区、推荐、衣橱不自行建立另一套认证。

**认证与资料**

| 方法 | 路径 | 优先级 | 说明 |
|---|---|---|---|
| POST | `/auth/register` | P0 | `{email, password, nickname}`；成功 `data=null`，不签发 token，不自动登录；前端跳登录页 |
| POST | `/auth/login` | P0 | `{email, password}` → `{token, expiresIn, user}`；另通过 Set-Cookie 设置 refresh token |
| POST | `/auth/refresh` | P0 | 新增；读取 refresh Cookie，返回 `{token, expiresIn}`，并轮换 refresh Cookie；无需有效 access token |
| POST | `/auth/logout` | P0 | 撤销当前会话的两种 token，并清除 refresh Cookie |
| POST | `/auth/forgot-password` | P1 | `{email, newPassword}`；邮箱＋新密码直接重置，不使用验证码或恢复码；撤销该用户全部会话 |
| GET | `/me` | P0 | 获取当前用户资料，不返回密码哈希或会话凭据 |
| PATCH | `/me` | P1 | 仅接收 `nickname`、`email`、`avatarFileId`；只改传入字段，邮箱可直接修改 |
| POST | `/me/change-password` | P1 | 新增；已登录，提交 `{oldPassword, newPassword}`，验证原密码后修改并撤销该用户全部会话 |
| GET | `/users/:id` | P1 | 公开作者资料，不含邮箱及认证信息 |
| GET | `/dict` | P0 | 第 2 节枚举及已统一的颜色白名单，按编码/显示名称返回 |
| GET | `/config` | P0 | 前端功能开关；不返回密钥、数据库地址或内部文件路径 |

**关注 / 通知 / 偏好**

| 方法 | 路径 | 优先级 | 说明 |
|---|---|---|---|
| GET | `/me/posts` | P0 | 当前用户发布的帖子，返回分页帖子卡片 |
| GET | `/me/likes` | P0 | 当前用户点赞的帖子，返回分页帖子卡片 |
| GET | `/me/favorites` | P0 | 当前用户收藏的帖子，**仅帖子**，不混入心愿单品、本人常用单品或整套搭配 |
| GET | `/me/following`、`/me/followers` | P1 | 我的关注/粉丝，分页公开用户资料，可附当前用户是否已关注 |
| POST / DELETE | `/users/:id/follow` | P1 | 关注/取关，禁止关注自己；重复关注或重复取消均成功，不重复计数 |
| GET | `/notifications` | P1 | 本人的通知列表，按创建时间倒序分页 |
| PUT | `/notifications/:id/read` | P1 | 仅接收人可标记已读；重复标记成功 |
| GET / PUT | `/me/style-preferences` | P1 | 穿搭偏好；PUT 整体替换 `{styles, avoid_colors, notes}`，不是 PATCH |

#### 5.3.1 注册、登录及刷新示例

注册请求：

```json
{"email":"user@example.com","password":"用户输入的密码","nickname":"晓珊"}
```

注册成功：

```json
{
  "code": 0,
  "message": "注册成功，请登录",
  "data": null,
  "requestId": "req_register_example"
}
```

注册成功不设置 refresh Cookie、不创建登录会话。昵称必填；前端跳登录页，可以预填邮箱，不保留或回填密码。

登录请求：

```json
{"email":"user@example.com","password":"用户输入的密码"}
```

登录成功：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "token": "新生成的accessToken",
    "expiresIn": 7200,
    "user": {
      "id": "u_001",
      "email": "user@example.com",
      "nickname": "晓珊",
      "avatar_url": null,
      "following_count": 0,
      "follower_count": 0,
      "created_at": "2026-11-24T20:00:00+08:00"
    }
  },
  "requestId": "req_login_example"
}
```

`token` 固定指 access token，`expiresIn` 单位为秒；refresh token 只在 Set-Cookie 中传递。登录成功新建一条会话，不自动踢出其他设备。

刷新请求为 `POST /auth/refresh`，无 JSON 业务参数，不要求 access token；浏览器通过凭据选项携带 refresh Cookie。成功响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {"token":"刷新后的accessToken","expiresIn":7200},
  "requestId": "req_refresh_example"
}
```

同时轮换 refresh Cookie。示例中的 7200 是常见值，接近会话固定截止时间时返回实际剩余有效秒数。缺失、过期、撤销或已使用的 refresh token 返回 `40101`、`data=null`；不返回凭据、不泄露校验细节。

#### 5.3.2 读取与修改账号资料

`GET /me` 的 `data` 与登录成功的 `user` 结构一致；`GET /users/:id` 只返回可公开的 ID、昵称、头像、关注/粉丝数和页面需要的公开信息，不返回邮箱、密码哈希或会话数据。

`PATCH /me` 接收以下可选字段：

| 字段 | 含义 | 校验及更新规则 |
|---|---|---|
| nickname | 昵称 | 非空字符串，不能全为空格 |
| email | 新登录邮箱 | 登录后可直接修改，不验证原密码/邮箱验证码；格式有效且未被其他账号占用 |
| avatarFileId | 新头像的上传文件编号 | 文件存在、类型合规且属于当前用户；验证后更新 `avatar_url` |

未传字段不变；传 null 不作为清空操作，本版直接返回 `40001`；不提供删除头像的隐含语义。禁止提交 `id`、`user_id`、`password`、`password_hash`、关注数或粉丝数等不可编辑字段。注册和密码接口按统一密码校验规则处理；字段具体长度限制见 5.3.8 的当前实现清单；该清单须与前端同步确认，禁止一边接受而另一边拒绝。

示例：

```json
{"nickname":"新昵称","email":"new@example.com","avatarFileId":"file_avatar_01"}
```

修改成功返回完整更新后的本人资料（结构同 GET /me），不签发新凭据。邮箱修改不改变用户 ID、衣橱、帖子及关注关系；新邮箱是后续登录/找回密码的标识，旧邮箱不再登录此账号。当前及其他既有有效会话继续使用用户 ID，不因邮箱变更失效。该流程不代表新邮箱所有权已验证。

#### 5.3.3 修改密码、忘记密码与退出

**登录后修改密码：** `POST /me/change-password` 必须通过当前登录鉴权，请求为：

```json
{"oldPassword":"原密码","newPassword":"新密码"}
```

原密码错误返回 `40001` 并提示“原密码错误”，保持现有密码和会话不变，不触发前端自动刷新；新密码不合规则返回 `40001`。成功时在同一事务更新密码哈希并撤销该用户全部登录会话，返回 `code=0`、`message="密码修改成功，请重新登录"`、`data=null`，清除本设备 refresh Cookie；前端清除 access token 并跳登录页。其他设备的旧凭据也不能继续使用或刷新。

**忘记密码：** 沿用课程演示的 `POST /auth/forgot-password`，无需登录：

```json
{"email":"user@example.com","newPassword":"新密码"}
```

查找匹配账号，验证新密码格式后更新哈希，撤销该用户全部会话；成功返回 `code=0`、`message="密码重置成功，请登录"`、`data=null`，不自动登录。邮箱格式错误返回 `40001`，未找到账号返回 `40401`。接口只按邮箱定位目标账号，不会撤销其他账号的会话；本设备若恰好登录该目标账号则清除对应 refresh Cookie，前端成功后清除本地登录状态。

保留原范围说明：该找回方案不验证邮箱所有权，知道邮箱的人可能重置密码，**仅用于课程演示，不适用于正式上线**。本轮不增加恢复码、邮件验证码或新的邮件服务。登录、刷新、重置和修改密码请求均限频，超过限制返回 `42901`。

**退出：** `POST /auth/logout` 优先从有效 access token 定位当前会话；access token 已过期时可由有效 refresh Cookie 定位。若两种有效凭据同时存在，它们必须属于同一会话，否则返回 `40001`，不跨账号撤销。只撤销这一条会话，不影响其他设备。凭据已失效或缺失时仍返回成功并清除 refresh Cookie，退出操作保持幂等。成功 `data=null`，前端清除本地 access token。

#### 5.3.4 我的帖子、点赞和收藏

- `/me/posts` 只查询当前用户发布的帖子；`/me/likes` 只查询当前用户点赞的帖子；`/me/favorites` 只查询当前用户收藏的帖子。
- `GET` 使用第 4 节分页参数，成功 `data` 统一为 `{list, total, page, pageSize}`。`list` 中返回可直接展示的帖子卡片，字段沿用 5.4 信息流示例：`id`、`author`、`image_urls`、`text`、`like_count`、`comment_count`、`is_liked`、`is_favorited`、`created_at`。按相关记录时间倒序，时间相同按 ID 稳定排序；关系记录若尚无时间字段，由数据库负责人落实必要的排序字段。
- 他人的帖子已删除或不可见时，不在点赞/收藏列表中展示；`total` 也按当前可展示记录计算。我的帖子列表只返回本人仍存在的帖子。
- 收藏页不展示 `items.is_favorite`、`wish_items` 或推荐搭配；不增加收藏整套穿搭功能。帖子收藏写入/取消仍由社区既有 `/posts/:id/bookmark` 提供，账号列表读取同一份关系，不额外写另一张表。

#### 5.3.5 头像、字典和配置

**头像：** 复用衣橱的 `POST /uploads/image`。前端取得 `fileId` 后再提交 `PATCH /me` 的 `avatarFileId`；账号后端通过共用上传记录查询校验文件归属、存在性及图片类型，再保存头像地址，返回字段仍为 `avatar_url`。不允许前端提交任意 URL 来替代归属校验。上传接口负责人需同步头像用途、公开头像访问方式及文件限制；本节不改衣橱私密图片权限，不新增上传接口，具体限制由媒体负责人统一公布。

**字典：** `/dict` 使用第 2 节既有编码，返回编码/中文名称，例如 `data.categories=[{"value":"tops","label":"上装"}]`；统一键为 `categories`、`seasons`、`occasions`、`styles`、`colors`、`verifyStatuses`、`warmthLevels`、`visibilities`、`notificationTypes`、`reportTargetTypes`、`itemSources`。`itemSources` 指 2.11 的 `owned/wish`，不替代 items 表 `manual/ai` 的录入方式。颜色白名单由衣橱和推荐共同维护后交账号统一返回，不由账号另造；编码由校验层和前端共用。

**配置（已实现，待前端同步确认）：** `/config` 当前返回以下四个布尔键，均位于统一响应的 `data` 内：

| 键 | 当前含义 | 本地默认 |
|---|---|---|
| accountEnabled | 账号模块可用 | true |
| myPostListsEnabled | 社区帖子列表适配器已接入 | false |
| avatarUpdateEnabled | 头像文件查询适配器已接入 | false |
| colorPreferencesEnabled | 已配置团队确认的颜色白名单 | false |

以上键不是此前共同文档已确定的名字，本轮将其列出供前端确认；若前端已有开关命名，双方先统一再改代码/文档。适配器“已接入”不代表业务已经通过验收。响应不得包含模型 Key、数据库连接串、内部目录或其他凭据；开关只控制展示，不替代服务端权限校验。当前实现的 `/dict`、`/config` 均要求登录，符合第 4 节私有接口默认规则；如前端需要登录前获取，另行确认公开例外，不擅自放开。

**颜色白名单的当前状态：** `/dict` 的 `colors` 在未配置时返回 `[]`，穿搭偏好此时仅接受 `avoid_colors=[]`。允许独立保存风格和备注；提交非空避开颜色返回 `40001`，不偷偷接受账号自造色名。衣橱/推荐提供共同白名单并配置后，再启用颜色选项。该状态是缺少交接数据，不等于完整颜色功能已交付。

#### 5.3.6 跨模块分工与兼容路径

- **账号负责对外“我的列表”，社区提供帖子查询能力。** `/me/posts`、`/me/likes`、`/me/favorites` 使用社区维护的帖子/点赞/收藏数据，通过同一工程内部方法衔接，不另起 HTTP 服务、不复制收藏写入逻辑。具体函数名、导入路径由双方在共用工程固定。
- **重复路径的兼容方案待社区负责人确认。** 本轮账号前端统一使用 `/me/likes` 和 `/me/favorites`；5.4 中原有 `/me/liked-posts`、`/me/bookmarked-posts` 保留原文，不由账号单方面删除。若社区确认保留为兼容别名，应复用相同查询、权限和响应，不能另建业务；若决定删除，再同步改 5.4、5.7。P0 的“我的列表”交付不应依赖另做一套 P1 列表。
- **通知：** 账号提供通知创建能力，社区点赞/评论成功后调用，关注通知由账号在关注成功时创建。不向自己的操作生成通知，重复点赞/关注不重复通知；通知写入仅发生在关系实际变化时。仅接收人可读自己的通知和标记已读；目标内容删除后保留通知记录，跳转提示不可用。具体内部方法名由双方固定。
- **关注：** 账号维护 follows 及用户关注/粉丝计数，关系和计数同事务更新；社区前端调用既有关注接口，不另写一套关注后端。
- **偏好：** GET 未设置时返回 `{styles:[], avoid_colors:[], notes:""}`；PUT 接收全部三个字段并整体替换，数组校验第 2 节字典，不传字段不得隐式保留。推荐模块通过统一读取方法获取偏好，实际如何影响排序仍由推荐负责。
- **共同交付：** 账号提供可信当前用户依赖及对接示例；数据库负责人落实 3.1.1 的会话表；上传负责人提供文件归属查询。现有技术栈/数据库选型的待确认项保持原状，本轮不擅自确定其他模块实现。

#### 5.3.7 账号错误与前端处理

| 场景 | code | 前端行为 |
|---|---|---|
| 邮箱/密码/昵称等参数格式不正确 | 40001 | 表单提示，不触发刷新 |
| 注册或修改邮箱时邮箱已被其他账号占用 | 40901 | 显示邮箱占用提示，不能静默吞掉 |
| 登录邮箱或密码不匹配 | 40101 | 登录表单提示“邮箱或密码错误”，不触发刷新 |
| 私有业务 access token 无效或过期 | 40101 | 按 4.4 发起一次共享刷新，原请求最多重试一次 |
| refresh token 缺失、过期或撤销 | 40101 | 清除登录状态并跳登录页，不递归刷新 |
| 已登录修改密码时原密码错误 | 40001 | 显示原密码错误，不撤销会话 |
| 找回密码时邮箱对应账号不存在 | 40401 | 提示未找到账号 |
| 无法读取上传记录或数据库/服务内部异常 | 50001 | 通用错误提示，保留 requestId，不假装保存成功 |
| 请求过频 | 42901 | 提示稍后重试 |

头像文件不存在或不可用于本人时返回 `40401`，文件类型或其他字段不合规则返回 `40001`；不向无权限者泄露文件是否属于另一个用户。以上业务码沿用第 4 节；账号接口 HTTP 状态建议与参数错误 400、认证错误 401、不可见 404、冲突 409、限频 429、内部错误 500 对齐，成功使用 200。网络层故障、HTTP 状态与业务码均需前端处理，不把所有错误都解释成需要刷新。


#### 5.3.8 请求校验的当前实现参数（待前端同步确认）

下表记录 `account_backend_v1` 实际校验，补齐原文没有给出具体数值的部分；不是新的业务功能，也不改变字段名。前后端统一确认后按同一值校验，若要调整应同步代码、OpenAPI和本文。

| 字段/场景 | 当前校验 |
|---|---|
| 注册 password、忘记密码 newPassword、修改密码 newPassword | 字符串，8～128字符；不隐式去除密码空格 |
| 登录 password、修改密码 oldPassword | 字符串，1～128字符；按账号哈希验证，不强制旧凭据重新满足新密码最小长度 |
| nickname | 首尾去空格后1～30字符，不能全空格 |
| email | 常见ASCII邮箱，总长度≤254，本地部分≤64；去首尾空格并统一转小写，注册/登录/修改/找回使用相同规则 |
| avatarFileId | 非空字符串，1～128字符；真实文件的类型/大小仍由上传模块确定 |
| styles | 数组，最多7项，每项取2.4枚举；重复值保存时去重 |
| avoid_colors | 数组，最多30项，每项取共同颜色白名单；重复值保存时去重 |
| notes | 字符串，最多500字符，可为空字符串 |
| PUT /me/style-preferences | styles、avoid_colors、notes三个字段都必须提供，整体替换 |
| 账号JSON请求额外字段 | 拒绝未定义字段，返回40001；不能用userId/角色等额外字段越权 |
| PATCH /me | 未传字段不变；显式null返回40001，不视为清空 |
| 分页 | page≥1；pageSize为1～100，默认20，沿用第4节 |

风格本身在既有文档里就是数组，正式前端应支持多选。验收页当前一次选择一种风格，只是测试页面的简化，不将后端改成单值。

#### 5.3.9 通知列表返回与内部创建（待相关负责人同步确认）

`GET /notifications` 仍按第4节分页，data为 `{list,total,page,pageSize}`。每条保留3.8既有字段：`id`、`user_id`、`type`、`from_user_id`、`target_type`、`target_id`、`is_read`、`created_at`。当前代码额外附带公开触发人资料 `from_user`，供前端直接展示头像/昵称，不包含邮箱或认证数据。

`from_user` 的当前字段为 `id`、`nickname`、`avatar_url`、`following_count`、`follower_count`、`created_at`，与公开用户资料结构一致；该扩展须与前端同步。内部去重字段 `event_key` 不返回。

关注通知示例（仅展示一条通知对象，外层仍为分页和统一响应）：

```json
{
  "id": "ntf_example",
  "user_id": "u_receiver",
  "type": "follow",
  "from_user_id": "u_sender",
  "target_type": "user",
  "target_id": "u_sender",
  "is_read": false,
  "created_at": "2026-11-25T09:00:00+08:00",
  "from_user": {
    "id": "u_sender",
    "nickname": "测试用户",
    "avatar_url": null,
    "following_count": 1,
    "follower_count": 0,
    "created_at": "2026-11-25T08:00:00+08:00"
  }
}
```

通知的 `target_type` 与举报对象枚举不是同一个字段口径：关注通知当前跳转 `user`；点赞/评论的具体跳转对象及参数须与社区确认，不能把“通知ID”当作发起人ID。此处不改第2.10的举报枚举。

本地内部方法为 `app.modules.account.service.create_notification(conn, *, receiver_id, sender_id, kind, target_type, target_id, event_key, now)`：不自行提交事务、不通知自己、相同event_key不重复写。社区在实际关系/评论创建成功的同一事务调用；数据库和工程适配前，不要求队友直接照搬本地sqlite连接和方法名。

#### 5.3.10 首版本地实现与团队交接状态

| 项目 | 目前状态 | 团队接入要求 |
|---|---|---|
| 注册/登录/刷新/退出、资料/邮箱修改、改密/找回 | 已实现并测试 | 正式前端按约定请求与Cookie行为对接 |
| 关注/粉丝、通知查询/已读、风格和备注偏好 | 已实现并测试 | 通知创建与推荐读取偏好通过内部能力连接 |
| GET /me/posts、/me/likes、/me/favorites | 路由和查询契约存在，真实社区查询未接入 | 社区提供分页帖子卡片，收藏仅帖子；不得拿本地空数据当联调通过 |
| PATCH /me 的 avatarFileId | 字段和归属校验接入口存在，真实文件查询未接入 | 上传提供本人可用头像URL解析，不新增另一套上传接口 |
| colors及avoid_colors非空选择 | 等待共同颜色白名单 | 由衣橱/推荐给出后同步字典与校验 |
| SQLite/sqlite3、表结构初始化 | 仅本地运行适配 | 团队最终数据库/ORM/迁移仍按4.3确认，不各自创建独立users数据库 |
| /config四个键、字段长度、from_user扩展 | 当前代码实际值已列明 | 前端同步确认后固定；不一致时修改相应代码 |
| event_key字段及通知方法 | 本地去重实现 | 数据库/社区确认迁移或等价方案，确认前不强推 |

尚未接入的帖子查询或头像查询，本地运行版返回HTTP503、业务code50001、data=null并说明“尚未接入”，这是临时联调状态，不新增业务错误码、不代表接口已完成业务验收。成功连接后应返回正常业务结构；实际文件不存在/不可用按40401，格式错误按40001；已接入服务内部异常按50001处理。

当前接入口为 `CommunityGateway.list_posts(conn, *, user_id, kind, page, page_size)`（kind为posts/likes/favorites，返回分页卡片）和 `UploadsGateway.resolve_avatar(conn, *, user_id, file_id)`（返回本人可用的头像URL）。类名、文件路径及数据库连接对象属于本地代码；最终内部命名随公共工程统一，对外HTTP路径和字段保持本文约定。

验收页的“输入用户ID/通知ID”“手动刷新”等只方便开发测试，不是正式产品交互要求。正式前端应从列表数据取得这些ID后自动提交，不要求用户手输。


## 公共应用合并补充（2026-11-26）

账号已与 main 的衣橱和社区整合到单一 `app.main:app`，共用 DATABASE_URL。保留原作者和帖子并补齐账号列；旧演示作者不会自动获得邮箱、密码或会话。真实 token 可跨模块使用，关注写入兼容社区已有 PUT 方法，统一由账号维护计数。账号配置类移至 `app.modules.account.settings`，公共配置保持 `app.core.config.Settings`。头像关联和我的帖子列表查询仍待接入。合并回归 89 项通过，细节见 backend/docs/TEST_REPORT.md。
