# 衣搭后端

衣搭后端采用 FastAPI、SQLAlchemy 2 和 SQLite。公共 FastAPI 应用当前接入衣橱与社区模块；推荐模块保留自己的联调工具，后续按统一接口接入。

## 多人协作目录约定

后端只有一个 FastAPI 应用，公共入口和基础设施不得由每个功能模块重复创建：

- `app/main.py`：唯一应用入口，原则上保持稳定。
- `app/api.py`：统一注册各业务模块路由；新增模块时只在这里增加一次注册。
- `app/core/`：共用配置、数据库会话、认证依赖、响应和异常处理。
- `app/modules/<模块名>/`：各功能自己的路由、模型、字段校验和业务逻辑。
- `requirements.txt`、`.env.example`：全后端共用，不在模块目录再建一份。

账号、社区、推荐功能应分别新增 `modules/account/`、`modules/community/`、`modules/recommendation/`，不要再创建新的 `main.py`、数据库连接或独立 FastAPI 服务。修改 `app/api.py`、`app/core/`、依赖清单或数据库迁移前，需要先和相关负责人同步。

## 已接入模块

- `app/modules/wardrobe/`：衣物上传、识别、分类、编辑、心愿衣橱和权限控制。
- `app/modules/community/`：信息流、帖子详情、评论、点赞、收藏和关注，已经注册到公共 FastAPI 入口。
- `recommendation/`：推荐服务的联调实现、真实天气、规则推荐与课程测试集。运行方法见 [recommendation/README.md](recommendation/README.md)，商品图片使用范围见 [recommendation/fixtures/garment/README.md](recommendation/fixtures/garment/README.md)。

## 本地启动

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:APP_ENV = "development"
$env:WARDROBE_AI_PROVIDER = "mock" # 仅用于体验 AI 状态流转
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- 接口文档：<http://127.0.0.1:8000/docs>
- 衣橱调试页：<http://127.0.0.1:8000/debug/wardrobe>
- 健康检查：<http://127.0.0.1:8000/health>

调试页使用 `dev:<用户ID>` 格式的 Bearer Token。该格式只在 `APP_ENV=development` 时有效；生产环境必须由账号模块替换 `app.core.auth.get_current_user_id`。

## 测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

测试套件同时包含接口/服务回归和 Playwright 浏览器端到端测试。浏览器测试会优先使用本机安装的 Chrome，其次使用 Edge，真实点击调试页完成分类筛选、分页、上传、编辑、收藏、删除、AI 状态流转、心愿单和身份切换。

## 演示数据与视频

仓库内的 `demo_assets/realistic/` 保存可复现的衣物示例图片。以下命令会先把当前 SQLite 数据库和上传文件备份到 `data/backups/`，再重建固定演示数据：

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\reset_demo_data.py
```

服务运行后，可执行以下命令录制完整浏览器演示。视频输出到被 Git 忽略的 `data/demo-output/`，不会进入提交：

```powershell
.\.venv\Scripts\python.exe -m playwright install ffmpeg
.\.venv\Scripts\python.exe scripts\record_full_demo.py
```

SQLite 数据库和上传文件默认保存在 `backend/data/`，该目录已被 Git 忽略。
