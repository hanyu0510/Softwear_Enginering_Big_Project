# 衣搭穿搭推荐模块（独立联调实现）

本模块依据项目开发公约 `dev-alignment-doc(1).md` 的第 2、3.4、3.10–3.12、4、5.5 节实现，使用 Python 3.11+ 标准库和 SQLite，`requirements.txt` 无额外安装项。当前代码可独立运行；团队账号、衣橱和数据库模块合并后，正式模式需要接入相应适配器。

## 已实现

- 八个正式推荐接口，统一 `/api/v1` 前缀、数字业务码、`requestId`、Bearer 身份入口。
- 城市搜索和按日期查询天气。真实模式通过 [Open-Meteo 地理编码](https://open-meteo.com/en/docs/geocoding-api)和[预报 API](https://open-meteo.com/en/docs)获取城市及预报；城市 ID 使用 `om_<地理编码ID>`。天气失败或超出 14 天时，独立天气接口报 `50301`，推荐接口无天气降级。
- 本地常见词解析和可选模型解析。模型输出按固定 Schema、枚举和色卡校验。八种潮流风格中的常见词可在无模型时得到基础映射，未知词标低置信度。
- 确定性硬约束、分类候选、结构化搭配、可配置加权评分、智能叠穿、锁定单品、换一套、心愿提示、历史快照、反馈覆盖。
- 可选 JSON 模型精排。模型只能在后端给出的候选索引中选择，非法输出最多重试两次后回到规则结果。真实模式不会切换为模拟天气。

## 目录

| 文件 | 职责 |
| --- | --- |
| `api.py` | HTTP 路由、Bearer 入口、统一响应和错误 |
| `contracts.py` | 请求、日期、枚举、解析结果校验 |
| `providers.py` | Open-Meteo、模拟天气、兼容 JSON 的模型适配 |
| `repositories.py` | 推荐自有 SQLite、跨模块 `WardrobePort`、模拟衣橱 |
| `engine.py` / `config.py` | 规则评分、结构化组合、候选复核、权重 |
| `service.py` | 推荐流程、解析回退、天气降级、持久化 |
| `prompts.py` | 解析和精排独立 System Prompt |
| `test_recommendation.py` | 规则、服务、HTTP 集成测试 |

算法和四张 Mermaid 图见 [recommendation-design.md](../../docs/recommendation-design.md)，契约争议见 [recommendation-contract-issues.md](../../docs/recommendation-contract-issues.md)。

## 启动与配置

在仓库的 `backend` 目录运行：

```powershell
$env:RECOMMENDATION_MODE = 'mock'
python -m recommendation.api
```

服务默认监听 `127.0.0.1:8010`，可设 `RECOMMENDATION_HOST` / `RECOMMENDATION_PORT`。模拟模式接受 `mock-token-u1` 和 `mock-token-u2`，内含两名**模拟**用户、至少 30 件模拟衣物及模拟城市天气，`source=MOCK_TEST_ONLY`。推荐结果写入 `recommendation/data/recommendation.sqlite3`，被仓库 `.gitignore` 排除。配置样例见 `.env.example`；标准库版本不会自动加载 `.env`，须把值设为进程环境变量。

启动后打开 <http://127.0.0.1:8010/>，即可使用浏览器联调台。页面可切换两名模拟用户、搜索旅行城市、预览场景解析、生成或重生成搭配、查询天气、查看历史和提交反馈。测试页在 `mock` 和 `catalog_live_weather` 模式提供；`mock` 模式中的衣物名称及天气均为模拟数据。

要试用**本地商品图片 + 真实天气**，改用：

```powershell
$env:RECOMMENDATION_MODE = 'catalog_live_weather'
python -m recommendation.api
```

默认读取仓库内 `backend/recommendation/fixtures/garment/garments.sqlite` 和图片；如需使用其他本地数据，设置 `GARMENT_DATASET_DIR`。在 Windows 上也可双击 `run_catalog_demo.cmd`，然后打开 <http://127.0.0.1:8011/>。该模式只监听本机回环地址，仍使用模拟账号 Token。商品样本映射为虚拟测试用户假设拥有的衣服，并用图片展示；其性质与字段映射见 [garment-fixture.md](../../docs/garment-fixture.md)。实时天气需要能访问 Open-Meteo；若供应商不可用，页面会显示错误或给出无天气降级推荐，不会用模拟温度充当实况。

真实模式：

```powershell
$env:RECOMMENDATION_MODE = 'live'
python -m recommendation.api
```

真实模式不接受模拟 token。团队账号/衣橱负责人应实现 `WardrobePort` 的 `current_user(token)`、`items(user_id, include_wish)`、`preferences(user_id)`、`current_city_id(user_id)`、`still_available(user_id, source, id)`，并在团队服务注册时通过 `create_app(wardrobe=...)` 注入。`items` 必须按本人过滤，返回契约字段；心愿记录必须带 `available` 和 `source_visibility`。模块还会二次核对 `user_id` 和保存前可用性。不得把 `UnconfiguredWardrobe` 当作生产实现。

推荐自有表为 `outfits` 和 `recommendation_feedback`；初始化由 `OutfitStore` 完成，字段与契约语义一致，数组和快照暂存 JSON TEXT。团队 PDM 出来后，仅替换 `OutfitStore`，并协调数据库负责人迁移；本模块不更改账号/衣橱表。`cities` 当前由提供方地理编码 ID 解析，不建团队城市表，后续可替换 `city_weather` 注入适配器。

真实天气默认走 Open-Meteo 公开端点，可设置 `WEATHER_BASE_URL`、`WEATHER_TIMEOUT_SECONDS`，服务层仍限制为今日至今日后 14 天，并受实际供应商范围约束。城市搜索返回同名城市的国家、区域及坐标供前端选择。`observedAt` 暂代表取得预报的时间，`forecast=true`，不冒充现场观测。`WEATHER_API_KEY` 留给后续供应商；当前 Open-Meteo 适配器不使用该值。第三方失败不会产生假温度。

模型使用 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS`。端点应兼容 `POST <base>/chat/completions` 和 `response_format=json_object`。无 Key 时使用本地解析与纯规则推荐。Prompt 不允许用户文本更改指令，服务端只给模型有限候选，模型不能自行查询衣橱。供应商若不兼容，替换 `LLMProvider`；密钥仅放服务端环境变量。

## API 联调

所有推荐接口须带 `Authorization: Bearer <token>`。成功响应是 `{code:0,message:"ok",data:{...},requestId:"req_..."}`；失败时 `data:null`。例如在模拟模式：

```powershell
$headers = @{ Authorization = 'Bearer mock-token-u1'; 'Content-Type' = 'application/json' }
Invoke-RestMethod 'http://127.0.0.1:8010/api/v1/cities?keyword=苏州' -Headers $headers
Invoke-RestMethod 'http://127.0.0.1:8010/api/v1/weather?cityId=city_suzhou&date=2026-11-24' -Headers $headers
$body = @{ sceneText='去公园野餐拍照'; styleText='美拉德'; wardrobeScope='owned' } | ConvertTo-Json
Invoke-RestMethod 'http://127.0.0.1:8010/api/v1/recommendations' -Method Post -Headers $headers -Body $body
```

| 方法 | 路径 | 请求与响应重点 |
| --- | --- | --- |
| GET | `/cities?keyword=&country=` | 城市数组；`cityId/cityName/region/country/lat/lng` |
| GET | `/weather?cityId=&date=` | 天气对象；范围或供应商异常 `50301` |
| POST | `/recommend/scene-parse` | `{sceneText?,styleText?}` → 固定 `parsed` 结构 |
| POST | `/recommendations` | 四类输入组合 → `id,parsed,items,warnings,local_tips,reason,weather,modelStatus` |
| POST | `/recommendations/{id}/regenerate` | `{locked_items?:[{source,id}]}` → 新推荐 ID |
| GET | `/recommendations/{id}` | 本人详情、原始输入、生成时间及单品可用性 |
| GET | `/recommendations?page=&pageSize=` | `{list,total,page,pageSize}`，每页最多 100 |
| PUT | `/recommendations/{id}/feedback` | `{preference:"like"|"dislike",reason?}` → `{preference,savedAt}` |

生成请求示例：

```json
{
  "sceneText": "去公园野餐拍照",
  "styleText": "美拉德",
  "destination": {"cityId": "city_suzhou"},
  "travelDate": "2026-12-05",
  "date": "2026-12-05",
  "wardrobeScope": "owned_and_wish",
  "locked_items": [{"source": "owned", "id": "item_mock_u1_1"}]
}
```

其中模拟日期仅为测试示例，运行时需选择当天至 14 天内的日期。`destination` 和 `travelDate` 要同时出现，`date` 若同时出现必须相同。本地模式只接受当日。日期超出预报范围时，生成接口返回带 warning 的无天气搭配，`weather=null`。没有当前城市时也会明确提示。缺项与空衣橱不编造单品；模型失败时 `modelStatus=rule_based`。

API 描述见 `openapi.yaml`；可直接导入 `postman_collection.json` 测试八个接口。正式服务需使用团队统一 HTTPS 入口及 Token 机制，独立示例只在回环地址提供 HTTP 开发联调。

## 测试与已知限制

```powershell
cd backend
python -m unittest recommendation.test_recommendation -v
```

测试使用模拟数据，不调用真实天气或真实模型。需另用团队凭据与网络环境做真实提供方联调。当前仓库没有账号认证服务、正式衣橱表、用户当前城市服务和数据库 PDM，因而真实模式不能独立完成生成；这几个适配入口已明确保留。当地特色建议在无模型时只给通用步行/拍照建议，不生成未经验证的地点事实。`modelStatus`、历史分页字段及天气降级状态仍待团队确认。
