# 我的衣橱后端联调说明

本文记录衣橱后端已经实现的接口、运行方法和跨模块接缝。字段与错误码以组内《开发对齐文档》为准。

## 启动与调试页

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:APP_ENV = "development"
$env:WARDROBE_AI_PROVIDER = "mock"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- 衣橱调试页：`http://127.0.0.1:8000/debug/wardrobe`
- Swagger：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

开发环境临时使用 `Authorization: Bearer dev:<用户ID>`。例如用户 A 使用 `dev:user_a`，用户 B 使用 `dev:user_b`。此格式在生产环境不可用，账号模块完成后需要替换 `app.core.auth.get_current_user_id`。

`WARDROBE_AI_PROVIDER=mock` 只模拟“识别中→待确认→用户修改→确认”的状态流转，返回低置信度 `other`，不声称真实识别了图片。未配置或设为 `disabled` 时，识别接口返回 `50002`，其余衣橱功能仍可使用。

## 已实现接口

所有 JSON 成功响应为：

```json
{"code": 0, "message": "ok", "data": {}, "requestId": "req_xxx"}
```

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/uploads/image` | 上传 JPEG、PNG 或 WEBP，校验真实图片并生成缩略图 |
| GET | `/api/v1/uploads/{fileId}` | 受控读取原图；`?variant=thumb` 读取缩略图 |
| GET | `/api/v1/items` | 当前用户列表，支持类别、季节、颜色、关键词和分页 |
| POST | `/api/v1/items` | 使用已上传的 `imageFileId` 手动新增并直接确认 |
| GET | `/api/v1/items/{id}` | 本人可看全部状态；他人只能看已确认的公开单品 |
| PATCH | `/api/v1/items/{id}` | 只更新实际传入字段，支持 `is_favorite` |
| DELETE | `/api/v1/items/{id}` | 软删除，保留图片和历史引用基础 |
| POST | `/api/v1/items/{id}/confirm` | 把 AI 待确认记录改为 `confirmed` |
| POST | `/api/v1/ai/recognize` | 使用 `imageFileId` 建立识别记录 |
| POST | `/api/v1/ai/retry/{itemId}` | 重试本人处于 `failed` 的识别记录 |
| GET / POST | `/api/v1/wish-items` | 查询心愿衣橱、收藏他人公开单品 |
| DELETE | `/api/v1/wish-items/{id}` | 删除本人的心愿记录 |
| POST | `/api/v1/wish-items/{id}/copy-to-wardrobe` | 在来源仍公开时复制图片和字段到本人衣橱 |

## 两条新增流程

### 手动新增

1. `POST /api/v1/uploads/image`，保存响应中的 `fileId`。
2. `POST /api/v1/items`，把该值作为 `imageFileId` 提交。
3. 新记录为 `source=manual`、`verify_status=confirmed`。

### AI 建议后确认

1. 上传图片取得 `fileId`。
2. `POST /api/v1/ai/recognize`：`{"imageFileId":"file_xxx"}`。
3. 成功后记录为 `pending`；先用 `PATCH /items/{id}` 修正字段。
4. `POST /api/v1/items/{id}/confirm` 后才变成 `confirmed`。
5. AI 不可用时返回 `50002`；同一个 `imageFileId` 可以立即改走手动新增，旧失败记录会软删除，其他接口不受影响。

## 当前跨模块接缝

- 账号模块：替换开发认证依赖，返回可信 `user_id`；不得从请求体读取用户 ID。
- 数据库模块：当前统一采用 SQLite 和 SQLAlchemy 2，表为 `uploaded_files`、`items`、`wish_items`。后续正式迁移脚本应由数据库负责人接管。
- 推荐模块：调用 `app.modules.wardrobe.service.list_recommendation_candidates`，支持 `owned` 和 `owned_and_wish`，只返回已确认自有衣物及合法可用的心愿单品。
- 社区模块：收藏公开单品应复用 `/wish-items` 的业务，不要与 `/favorites` 双写两份记录。
- 前端模块：正式页面可参考调试页的请求方式，但调试页不替代正式 Vue 衣橱页面。

## 测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

自动化测试覆盖：统一响应、鉴权、真实图片校验、组合筛选、分页、枚举校验、A/B 用户隔离、公开媒体读取、PATCH、软删除、AI 状态流转、无 AI 降级、心愿去重、来源失效、复制到衣橱和推荐候选读取。
