# 衣搭后端

此目录用于衣搭的 Python、FastAPI 和 SQLite 后端。

## 账号模块第一版

按《开发对齐文档_账号模块修订版》中的账号约定实现，本次在独立功能分支提交，尚未接入社区与衣橱真实查询。
这是可以迁入团队工程的后端模块，不是整款穿搭软件，也没有替队友实现社区或衣橱。

## 一、先运行起来（你的 Windows / Python 3.12）

1. 将整个压缩包解压到新文件夹，进入包含 run.py、requirements.txt 的 backend 文件夹。
2. 在资源管理器地址栏输入 cmd 并回车。
3. 依次执行：

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

浏览器打开 **http://127.0.0.1:8002** 。这次端口是8002，不是前两个 demo 的8000/8001。
保持终端开启；不要双击HTML。以后启动只需执行最后一条命令，Ctrl+C停止。
也可以双击 START_WINDOWS.bat 自动完成安装并启动。
如果没有3.12版本但装有其他兼容版本，第一条用 py -m venv .venv；本包验证环境为Python3.12。

若8002被占用，先停止旧进程，或运行：

```bat
.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8003
```

此时访问 http://127.0.0.1:8003 。不要开放公网：本期忘记密码按需求直接用邮箱重置，不验证邮箱所有权。

## 二、先验收这条主流程

网页是本机接口验收页，用来替你手动发请求，不是正式产品前端：

1. 输入邮箱、昵称、密码（8～128字符），注册。注册成功跳到登录区域，不自动登录，不返回token。
2. 在登录区域输入密码并登录，页面显示用户ID；读取本人资料，检查响应。
3. 点击“手动验证刷新接口”，确认可正常轮换凭据。
4. 修改昵称/邮箱。当前会话仍能读取资料；退出后旧邮箱不能登录，改用新邮箱。
5. 修改密码时先故意输入错误原密码，应提示错误且不退出；输入正确原密码后成功，所有会话失效，需要重新登录。
6. 退出后用邮箱＋新密码进行忘记密码重置，再登录验证。不会发邮件、验证码或恢复码。
7. 用另一账号测试关注、粉丝和通知。建议用无痕窗口测试第二账号：同一浏览器普通标签页共享refresh Cookie，不能当作两个独立设备。
8. 填偏好并保存；停止后台，重新启动，资料和偏好仍在。

验收页隐藏登录凭据，只展示业务响应和requestId；access token存sessionStorage，refresh token由HttpOnly Cookie管理。
正式前端需在注册成功时用Vue Router跳转登录页；本验收页使用单页区域跳转，后端不会执行浏览器跳转。
验收页的“手动刷新”用于立即测试；真实access过期的自动刷新在JS中已实现，过期、并发、撤销行为用自动测试验证，不需要等待2小时。

## 三、已实现的接口

所有路径加前缀 `/api/v1`。成功和错误响应均含 code、message、data、requestId；错误data=null。

| 方法 | 路径 | 状态 |
| --- | --- | --- |
| POST | /auth/register | 创建账号，不建立会话 |
| POST | /auth/login | 创建独立会话，返回access，设置refresh Cookie |
| POST | /auth/refresh | 轮换两种凭据，截止时间不顺延 |
| POST | /auth/logout | 撤销当前会话，支持过期access时凭refresh退出，幂等 |
| POST | /auth/forgot-password | 邮箱＋新密码直接重置，撤销目标账号全部会话 |
| GET / PATCH | /me | 读取资料；修改昵称、邮箱和avatarFileId（头像需接上传适配器） |
| POST | /me/change-password | 验证oldPassword后修改，撤销全部会话 |
| GET | /users/{id} | 公开作者资料，不含邮箱和认证信息 |
| GET | /me/posts、/me/likes、/me/favorites | 已提供路由和查询接入口，等待社区实际查询；不伪造空列表 |
| POST / DELETE | /users/{id}/follow | 关注/取消；禁止自己；幂等；计数同事务更新 |
| GET | /me/following、/me/followers | 分页关注/粉丝列表，不暴露邮箱 |
| GET | /notifications | 仅本人的通知，分页；附公开触发人资料 |
| PUT | /notifications/{id}/read | 仅接收人可操作，重复已读成功 |
| GET / PUT | /me/style-preferences | 默认空值；PUT整体替换三个字段 |
| GET | /dict | 文档枚举；颜色等待团队白名单 |
| GET | /config | 返回本包已连接能力开关，不含私密配置 |

密码、改邮箱、忘记密码的行为严格按已确认需求；没有添加邮箱验证、恢复码或注册自动登录。
当前 /dict 和 /config 要求登录；若正式前端需要登录前取全局配置，需双方先同步文档的公开接口例外。
没有擅自实现社区的兼容列表路径 /me/liked-posts、/me/bookmarked-posts；由社区负责人确认是否以别名保留。

## 四、数据库与文件结构

首次启动自动建立 `data/account.db`，仅包含账号拥有的五张表：users、auth_sessions、follows、notifications、style_preferences。
不建立posts/items/files等队友模块表，不导入前面demo的数据。
目前使用Python自带sqlite3完成SQLite运行适配，不需要安装MySQL。最终数据库和ORM尚待团队确认，合并时需接公共数据库连接/迁移，不能与另一个账号数据库并行使用。
初版schema可查看 docs/schema.sql；它与运行代码一致。不要在现有团队数据库上直接执行未经对齐的SQL。

| 文件 | 主要作用 |
| --- | --- |
| run.py | 本机启动，一个FastAPI应用 |
| app/main.py | 路由注册、响应/异常、CORS、Origin检查、限流 |
| app/core/config.py | 环境配置 |
| app/core/database.py | 首版SQLite连接、事务、账号建表 |
| app/core/security.py | 密码哈希、随机token、token哈希、时间 |
| app/modules/account/router.py | 账号HTTP接口 |
| app/modules/account/schemas.py | 请求字段校验；拒绝额外字段 |
| app/modules/account/dependencies.py | 共用登录用户依赖 |
| app/modules/account/service.py | 会话、通知创建、偏好读取等内部能力 |
| app/modules/account/integrations.py | 社区和上传的接入契约 |
| app/modules/account/dictionaries.py | 既有枚举 |
| account_lab.html / account_lab.js | 仅本机验收页面与请求示例 |
| tests/test_account.py | 隔离临时数据库的自动验收 |
| docs/INTEGRATION.md | 与队友的代码接入位置和约定 |
| docs/openapi.json | 本包生成的接口描述，不含真实用户/凭据 |

## 五、自动刷新约定

- access token为安全随机字符串，默认2小时，响应字段仍是token；业务请求带 Authorization: Bearer ...。
- refresh token放HttpOnly Cookie，名称refresh_token，Path=/api/v1/auth，SameSite=Lax；HTTPS部署启用Secure。
- refresh期限为登录时刻起固定7天；每次刷新轮换access和refresh，旧值失效；接近截止时access寿命缩短。
- 退出只撤销当前会话；改/重置密码撤销账号全部会话；改邮箱不撤销会话。
- 所有会话存在数据库，重启不会悄悄清空；只保存token哈希，密码使用PBKDF2加随机盐。
- 前端并发401共享一个刷新请求，原请求最多重试一次；登录/注册/忘记密码/刷新本身不递归刷新。
- refresh凭据已失效才回登录页；网络或服务器异常只提示，不无限刷新、不误删账号资料。
- 登录、注册、刷新、找回、改密有单进程/IP限频，未采用Redis；多worker上线前须改统一限流存储。

## 六、如何和正式前端连接

前端使用你们统一的 `/api/v1` 路径，启用凭据携带：

```javascript
fetch('http://127.0.0.1:8002/api/v1/auth/login', {
  method: 'POST',
  credentials: 'include',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({email, password})
})
```

默认允许 http://127.0.0.1:5173 和 http://localhost:5173；前后端主机名要统一，不要前端localhost、后端127.0.0.1混用。
使用其他端口时，在启动程序前于同一个cmd窗口设置：

```bat
set "ACCOUNT_ALLOWED_ORIGINS=http://127.0.0.1:5174"
.venv\Scripts\python.exe run.py
```

程序读取系统环境变量；.env.example只是示例，不会自动加载。
正式前端可以参考account_lab.js的共享刷新处理，但应接回其现有网络请求层，不能同时维护两个互相竞争的刷新器。

## 七、需要队友连接的两部分

1. **头像**：上传负责人实现 resolve_avatar，检查fileId存在、归属、类型和公开头像访问方式，返回URL。不接入时PATCH头像返回HTTP503/code50001，其他资料修改仍能独立使用。
2. **帖子列表**：社区负责人实现 list_posts，复用自己的真实帖子/点赞/收藏数据，返回分页卡片。不接入时明确返回HTTP503/code50001，不会用空数组冒充已完成。

颜色白名单同样等衣橱与推荐提供；默认colors=[]、避开颜色仅接受空数组。可用环境变量ACCOUNT_COLOR_NAMES配置共同确认值，不把账号自造色名写进字典。
可单独保存偏好风格和备注，不影响账号主流程。
具体接入示例见 docs/INTEGRATION.md。没有上传接口的另一份实现，也没有社区写接口。

## 八、运行测试

在本项目目录运行：

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试用临时目录，结束后清理，不操作你在网页注册的账号。
覆盖注册不登录、邮箱归一/重复、原密码校验、token轮换与固定期限、并发刷新仅一次成功、过期access退出、跨设备会话撤销、修改邮箱保留会话、头像适配器归属、偏好、关注通知、跨账号权限、限流、CORS错误可读、未接入适配器的明确报错及重启持久性。
测试里的FakeUploads/FakeCommunity只用于验证接入契约，不出现在运行应用的默认接入中。
接口自动测试已运行；本机验收页面完成JavaScript语法检查，浏览器端点击交互仍需你本机验收，不把API测试当作完整浏览器测试。

## 九、边界说明

本轮按你们课程文档实现了“只凭邮箱重置密码”和“登录后直接改邮箱”。前者不验证身份、后者不验证新邮箱归属，仅用于本机课程验收。
后续要部署真实用户服务时需重新设计这两条流程；当前不加入未经你同意的验证码或恢复码。
本包仅监听127.0.0.1；可设置ACCOUNT_TEST_PAGE=false关闭验收页。
字段范围目前落实为：密码8～128字符、昵称1～30字符、备注≤500字符、常见ASCII邮箱≤254字符；它们是第一版实现参数，正式前端表单应同步同一范围。
未接入团队仓库、最终需求文档若有新版本或实际数据库不同，合并前再以它们校准；本次提交只包含源码、测试与说明，不含本地数据库、虚拟环境或真实凭据。
