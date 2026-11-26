"""只读地把本地商品样本映射为模拟用户衣橱；不改写原始数据库或图片。"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .contracts import COLORS
from .repositories import MockWardrobe

DEFAULT_DATASET = Path(__file__).resolve().parent / "fixtures" / "garment"
CATEGORY_MAP = {
    "tops": "tops", "long_sleeves": "tops", "graphic_tees": "tops",
    "sweatshirts_hoodies": "tops", "sweaters": "tops",
    "pants": "bottoms", "jeans": "bottoms", "shorts": "bottoms",
    "skirts": "bottoms", "intimates": "other",
}


def semantic_colors(raw: str) -> list[str]:
    """只转换商品字段中明确出现的颜色词，结果限于契约白名单。"""
    value = raw.casefold()
    rules = (
        ("white", "白"), ("cream", "米白"), ("beige", "米"),
        ("charcoal", "深灰"), ("dark grey", "深灰"), ("light grey", "浅灰"),
        ("grey", "灰"), ("gray", "灰"),
        ("black", "黑"), ("brown", "棕"), ("burgundy", "红"),
        ("maroon", "红"), ("red", "红"), ("pink", "粉"),
        ("light denim", "牛仔蓝"), ("dark denim", "牛仔蓝"),
        ("denim", "牛仔蓝"), ("navy", "藏青"),
        ("light blue", "浅蓝"), ("faded blue", "浅蓝"), ("blue", "蓝"),
        ("olive", "橄榄绿"), ("sage green", "绿"), ("green", "绿"),
        ("purple", "紫"), ("yellow", "黄"), ("orange", "橙"),
    )
    colors = []
    for word, color in rules:
        if word in value and color in COLORS and color not in colors:
            colors.append(color)
    return colors


class CatalogWardrobe(MockWardrobe):
    """公开商品映射给虚拟测试用户；owned 仅表示模拟测试中的假设拥有。"""
    def __init__(self, root: str | Path | None = None):
        super().__init__()
        self.root = Path(root or os.getenv("GARMENT_DATASET_DIR") or DEFAULT_DATASET).resolve()
        db_path = self.root / "garments.sqlite"
        if not db_path.is_file():
            raise FileNotFoundError(f"商品样本数据库不存在：{db_path}")
        self.paths: dict[str, Path] = {}
        with closing(sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT p.product_id,p.title,p.category,p.product_type,p.colors,
                       i.file_path FROM products p JOIN images i
                  ON i.product_id=p.product_id AND i.position=(
                      SELECT MIN(position) FROM images WHERE product_id=p.product_id)
                 ORDER BY p.product_id
            """).fetchall()
        catalog_items = []
        for row in rows:
            item_id = f"catalog_{row['product_id']}"
            relative = Path(row["file_path"])
            image = (self.root / relative).resolve()
            if not image.is_relative_to(self.root) or image.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp") or not image.is_file():
                continue
            try:
                variants = json.loads(row["colors"] or "[]")
            except json.JSONDecodeError:
                variants = []
            if not isinstance(variants, list):
                variants = []
            mapped = []
            for variant in variants:
                if isinstance(variant, str):
                    mapped.extend(c for c in semantic_colors(variant) if c not in mapped)
            # 多个可选颜色并不意味着首张图片同时有这些颜色，不给主色造值。
            primary_colors = semantic_colors(variants[0]) if len(variants) == 1 and isinstance(variants[0], str) else []
            primary = primary_colors[0] if primary_colors else None
            category = CATEGORY_MAP.get(row["category"], "other")
            if row["category"] == "sweaters" and "cardigan" in row["title"].casefold():
                category = "outerwear"
            self.paths[item_id] = image
            catalog_items.append({
                "id": item_id, "user_id": "mock_u1", "source": "owned",
                "name": row["title"], "image_url": f"/demo/images/{item_id}",
                "thumb_url": f"/demo/images/{item_id}", "category": category,
                "color": primary, "colors": mapped,
                "warmth": None, "material": None, "pattern": None,
                "season": [], "style": [], "occasion": [],
                "verify_status": "confirmed", "visibility": "private",
                "is_favorite": False, "deleted": False,
                "fixture_provenance": "public_catalog_simulated_ownership",
            })
        if not catalog_items:
            raise RuntimeError("商品样本中没有可用图片")
        # 原模拟衣橱仅保留商品目录缺少的类别，绝不把它们伪装成商品样本。
        support = {"shoes", "bag", "accessory", "outerwear"}
        self.records = [item for item in self.records
                        if item["user_id"] != "mock_u1" or item["source"] == "wish"
                        or item["category"] in support] + catalog_items
        self.catalog_count = len(catalog_items)

    def image_path(self, item_id: str) -> Path | None:
        return self.paths.get(item_id)
