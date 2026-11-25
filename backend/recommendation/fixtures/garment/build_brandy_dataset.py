"""Build a small, reproducible Brandy Melville US clothing image dataset.

Usage: python build_brandy_dataset.py [--per-category 4]
The script resumes existing downloads and rebuilds the SQLite/CSV indexes.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE = "https://us.brandymelville.com"
CATALOG_URL = f"{SOURCE}/products.json?limit=250&page=1"
CATEGORIES = {
    "tops": {"Tops", "Top", "Tanks", "Tank", "Halter", "tube top"},
    "long_sleeves": {"Long Sleeve"},
    "graphic_tees": {"Graphics", "T-Shirts"},
    "sweatshirts_hoodies": {"Hoodies", "Sweatshirts"},
    "sweaters": {"Sweaters"},
    "pants": {"Pants", "Sweatpants"},
    "jeans": {"Jeans"},
    "shorts": {"Shorts"},
    "skirts": {"Skirts"},
    "intimates": {"Underwear", "intimates"},
}


def plain_text(markup: str) -> str:
    text = re.sub(r"<\s*br\s*/?>", "\n", markup or "", flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def valid_image(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False


def download(session: requests.Session, url: str, path: Path) -> None:
    if valid_image(path):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    for attempt in range(3):
        try:
            with session.get(url, timeout=35, stream=True) as response:
                response.raise_for_status()
                if not response.headers.get("Content-Type", "").startswith("image/"):
                    raise ValueError(f"Unexpected content type: {response.headers.get('Content-Type')}")
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(65536):
                        output.write(chunk)
            if not valid_image(temporary):
                raise ValueError("Downloaded file is not a valid image")
            temporary.replace(path)
            time.sleep(0.2)
            return
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-category", type=int, default=4)
    args = parser.parse_args()
    if args.per_category < 1:
        parser.error("--per-category must be positive")

    session = requests.Session()
    response = session.get(CATALOG_URL, timeout=40)
    if response.status_code == 429:
        time.sleep(10)
        response = session.get(CATALOG_URL, timeout=40)
    response.raise_for_status()
    catalog = response.json()["products"]
    selected = []
    counts = {category: 0 for category in CATEGORIES}
    for product in catalog:
        for category, types in CATEGORIES.items():
            if product.get("product_type") in types and counts[category] < args.per_category:
                selected.append((category, product))
                counts[category] += 1
                break

    fetched_at = datetime.now(timezone.utc).isoformat()
    (ROOT / "source_products.json").write_text(
        json.dumps({"source": CATALOG_URL, "fetched_at": fetched_at,
                    "products": [p for _, p in selected]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Selected {len(selected)} products across {sum(bool(n) for n in counts.values())} categories", flush=True)

    db_path = ROOT / "garments.sqlite"
    connection = sqlite3.connect(db_path)
    connection.executescript("""
        DROP TABLE IF EXISTS images;
        DROP TABLE IF EXISTS products;
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
            product_type TEXT, description TEXT, product_url TEXT NOT NULL,
            price_min REAL, price_max REAL, currency TEXT NOT NULL,
            colors TEXT, tags TEXT, fetched_at TEXT NOT NULL
        );
        CREATE TABLE images (
            image_id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(product_id),
            position INTEGER NOT NULL, file_path TEXT NOT NULL, source_url TEXT NOT NULL,
            width INTEGER, height INTEGER, bytes INTEGER NOT NULL
        );
        CREATE INDEX idx_products_category ON products(category);
        CREATE INDEX idx_images_product ON images(product_id);
    """)
    csv_rows = []
    try:
        for number, (category, product) in enumerate(selected, 1):
            product_id = product["id"]
            product_url = f"{SOURCE}/products/{product['handle']}"
            variants = product.get("variants", [])
            prices = [float(v["price"]) for v in variants if v.get("price")]
            colors = sorted({v["option1"] for v in variants if v.get("option1")})
            connection.execute(
                "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (product_id, product["title"], category, product.get("product_type"),
                 plain_text(product.get("body_html", "")), product_url,
                 min(prices) if prices else None, max(prices) if prices else None,
                 "USD", json.dumps(colors, ensure_ascii=False),
                 json.dumps(product.get("tags", []), ensure_ascii=False), fetched_at),
            )
            for image in product.get("images", []):
                extension = Path(urlparse(image["src"]).path).suffix.lower()
                if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
                    extension = ".jpg"
                relative = Path("images") / category / str(product_id) / f"{image['position']:02d}_{image['id']}{extension}"
                path = ROOT / relative
                download(session, image["src"], path)
                connection.execute(
                    "INSERT INTO images VALUES (?,?,?,?,?,?,?,?)",
                    (image["id"], product_id, image["position"], relative.as_posix(),
                     image["src"], image.get("width"), image.get("height"), path.stat().st_size),
                )
                csv_rows.append({"category": category, "product_id": product_id,
                                 "title": product["title"], "product_type": product.get("product_type", ""),
                                 "price_min_usd": min(prices) if prices else "",
                                 "colors": " | ".join(colors), "product_url": product_url,
                                 "image_position": image["position"], "image_id": image["id"],
                                 "file_path": relative.as_posix(), "source_url": image["src"]})
            print(f"{number}/{len(selected)} {product['title']}: {len(product.get('images', []))} images", flush=True)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    with (ROOT / "images.csv").open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(csv_rows[0]) if csv_rows else [])
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Done: {len(selected)} products, {len(csv_rows)} images", flush=True)


if __name__ == "__main__":
    main()
