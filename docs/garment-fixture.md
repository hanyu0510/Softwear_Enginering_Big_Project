# 本地商品图片作为推荐内部测试集

数据源：课程项目收集的 Brandy Melville 商品样本，现存放于 `backend/recommendation/fixtures/garment`。包含 40 件商品、194 张图片及 10 个商品原类别。推荐模块以只读方式访问 `garments.sqlite` 与图片；不修改样本，也不把这些商品当成真实用户上传记录。

## 模拟身份与授权边界

`catalog_live_weather` 模式仅在本机回环地址提供页面。商品被映射给虚拟 `mock_u1`，`source=owned` 只表示**内部测试假设该虚拟用户拥有这些单品**。`mock_u2` 不会读取它们，真实账号和正式衣橱库也不会被写入。图片通过 `/demo/images/catalog_<商品ID>` 从已验证的本地文件映射读取，路由不接受任意磁盘路径。

源商品的公开网页不等于团队心愿衣橱里的“他人公开单品”，因此这些数据没有伪装成 `wish_items`。测试记录使用 `verify_status=confirmed` 表示此套**人工选定的测试夹具可参与推荐**；不表示真实用户已核对识图结果。正式用户数据仍要遵守确认流程。

## 字段转换

| 源商品类别 | 契约 `category` | 说明 |
| --- | --- | --- |
| tops、long_sleeves、graphic_tees、sweatshirts_hoodies、sweaters | `tops` | 标题明确含 Cardigan 的两件毛衫映射为 `outerwear` |
| pants、jeans、shorts、skirts | `bottoms` | 下装统一枚举 |
| intimates | `other` | 正式契约未设内衣枚举；规则组合不把它当作必要上装 |

商品 ID 转为 `catalog_<product_id>`，商品标题转 `name`，首张已下载图片转 `image_url`/`thumb_url`。单一变体里的明确英文颜色词映射到契约色卡，多个变体只保存 `colors` 候选而把主 `color` 留空。无法可靠确认的 `warmth`、`season`、`style`、`occasion`、`material`、`pattern` 保持 `null` 或空数组，不从图片或营销文案臆测。单品录入来源与推荐结果来源没有混用。

这批商品没有鞋、包、配饰或连衣裙。为了测试完整搭配，虚拟用户 1 仍带少量鞋、包、配饰及外套模拟补充单品；其上装和下装均来自商品样本。推荐结果中 `catalog_` 前缀及页面图片可识别商品样本。用户 2 保留少量纯模拟衣物用于隔离与缺项测试。

原图及其版权属于原权利人，图片不受项目根目录的 MIT 许可证约束。团队确认有将样本上传到本课程仓库的授权；其他人复用或商用须自行取得相应授权。推荐测试服务只在本机提供图片。

## 实际验证口径

自动测试检查数据库只读载入、40 件映射、白名单字段、用户隔离和本地图片路由。真实 Open-Meteo 调用另行执行联网验证；自动测试中的天气供应商依赖注入为确定性替身，不把模拟值标为真实天气。
