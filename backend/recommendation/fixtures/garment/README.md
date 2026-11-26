# Brandy Melville 衣物图片样本库

2026-11-24 从 [Brandy Melville 美国官网](https://us.brandymelville.com/)公开商品目录采集。首批覆盖 10 类衣物，每类 4 件，共 **40 件商品、194 张原始展示图**。对入选商品，已保存目录接口列出的全部图片；这批数据不是官网全量商品。

## 文件

- `images/`：按类别和商品 ID 存放的原始图片，未裁切或压缩。
- `garments.sqlite`：可查询的 SQLite 数据库。`products` 表包含名称、分类、描述、价格、颜色、标签及官网链接；`images` 表包含图片顺序、本地路径、来源 URL、尺寸和字节数。
- `images.csv`：一图一行的索引，适合直接用 Excel、Pandas 等打开。编码为 UTF-8 BOM。
- `source_products.json`：本次采集的官网商品原始数据快照。
- `build_brandy_dataset.py`：下载和重建索引的脚本；已存在且通过校验的图片会跳过。

本地图片示例：`images/tops/<商品ID>/<顺序>_<图片ID>.jpg`。CSV 和数据库里的 `file_path` 均相对于本文件夹。

## 使用

```powershell
python build_brandy_dataset.py --per-category 4
```

需要 Python 的 `requests` 和 `Pillow` 包。脚本从官网当前目录首页选择每类最新出现的指定数量商品，因此再次运行时，商品列表可能随官网更新而变化；`source_products.json` 保留本次实际采集快照。

查询示例：

```sql
SELECT p.title, p.category, p.price_min, i.file_path
FROM products AS p JOIN images AS i USING (product_id)
WHERE p.category = 'jeans' AND i.position = 1;
```

图片版权归原权利人，不适用仓库根目录的 MIT 许可证。项目成员确认有将这批图片上传到本课程仓库用于作业开发的授权；其他用途、再次分发或商用须自行取得相应授权。
