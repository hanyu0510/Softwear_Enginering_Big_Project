"""Back up and rebuild the local wardrobe demo database with deterministic data."""

from datetime import datetime
from pathlib import Path
from shutil import copy2, copytree, rmtree
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import BACKEND_DIR, get_settings
from app.core.db import SessionLocal
from app.main import app
from app.modules.wardrobe.models import Item, UploadedFile, WishItem


DATA_ROOT = (BACKEND_DIR / "data").resolve()
ASSET_ROOT = BACKEND_DIR / "demo_assets" / "realistic"


def auth(user: str) -> dict[str, str]:
    return {"Authorization": f"Bearer dev:{user}"}


def assert_safe_data_path(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(DATA_ROOT)
    if resolved == DATA_ROOT:
        raise RuntimeError("拒绝直接清理 data 根目录")
    return resolved


def back_up_and_clear() -> Path:
    settings = get_settings()
    db_prefix = "sqlite:///"
    if not settings.database_url.startswith(db_prefix):
        raise RuntimeError("演示重置脚本只允许操作本地 SQLite")
    db_path = assert_safe_data_path(Path(settings.database_url.removeprefix(db_prefix)))
    upload_dir = assert_safe_data_path(settings.upload_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = DATA_ROOT / "backups" / f"before-demo-reset-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    if db_path.is_file():
        copy2(db_path, backup_dir / db_path.name)
    if upload_dir.is_dir():
        copytree(upload_dir, backup_dir / "uploads")

    with SessionLocal() as session:
        session.execute(delete(WishItem))
        session.execute(delete(Item))
        session.execute(delete(UploadedFile))
        session.commit()

    upload_dir.mkdir(parents=True, exist_ok=True)
    for child in upload_dir.iterdir():
        if child.is_dir():
            rmtree(child)
        else:
            child.unlink()
    return backup_dir


def seed_demo() -> dict:
    settings = get_settings()
    settings.wardrobe_ai_provider = "mock"
    client = TestClient(app)

    def upload(user: str, asset: str) -> str:
        path = ASSET_ROOT / asset
        response = client.post(
            "/api/v1/uploads/image",
            headers=auth(user),
            files={"file": (path.name, path.read_bytes(), "image/png")},
        )
        response.raise_for_status()
        return response.json()["data"]["fileId"]

    def create(user: str, asset: str, **fields) -> dict:
        response = client.post(
            "/api/v1/items",
            headers=auth(user),
            json={"imageFileId": upload(user, asset), **fields},
        )
        response.raise_for_status()
        return response.json()["data"]

    items = [
        create(
            "user_a", "cream-knit.png", name="米白麻花针织衫", category="tops",
            color="米白", colors=["米白", "奶油色"], warmth=4, material="羊毛混纺",
            pattern="麻花针织", season=["autumn", "winter"], style=["minimal", "casual"],
            occasion=["commute", "casual", "date"], visibility="private",
        ),
        create(
            "user_a", "blue-jeans.png", name="复古水洗直筒牛仔裤", category="bottoms",
            color="中蓝", colors=["中蓝"], warmth=2, material="牛仔布", pattern="纯色",
            season=["spring", "autumn", "winter"], style=["street", "casual", "vintage"],
            occasion=["casual", "travel", "commute"], visibility="private",
        ),
        create(
            "user_a", "black-coat.png", name="黑色羊毛通勤大衣", category="outerwear",
            color="黑色", colors=["黑色"], warmth=5, material="羊毛", pattern="纯色",
            season=["autumn", "winter"], style=["minimal", "formal"],
            occasion=["commute", "formal", "date"], visibility="public",
        ),
        create(
            "user_a", "floral-dress.png", name="藏青碎花连衣裙", category="dress",
            color="藏青", colors=["藏青", "米白"], warmth=1, material="棉质", pattern="碎花",
            season=["spring", "summer"], style=["vintage", "sweet"],
            occasion=["date", "party", "travel"], visibility="public",
        ),
        create(
            "user_a", "white-sneakers.png", name="白色低帮休闲鞋", category="shoes",
            color="白色", colors=["白色"], warmth=1, material="帆布", pattern="纯色",
            season=["spring", "summer", "autumn"], style=["casual", "sporty", "minimal"],
            occasion=["casual", "travel", "sport"], visibility="private",
        ),
        create(
            "user_a", "brown-bag.png", name="棕色皮质单肩包", category="bag",
            color="棕色", colors=["棕色"], warmth=1, material="人造革", pattern="纯色",
            season=["spring", "summer", "autumn", "winter"], style=["vintage", "minimal"],
            occasion=["commute", "travel", "date"], visibility="private",
        ),
        create(
            "user_a", "burgundy-scarf.png", name="酒红色羊毛围巾", category="accessory",
            color="酒红", colors=["酒红"], warmth=4, material="羊毛", pattern="纯色",
            season=["autumn", "winter"], style=["vintage", "minimal"],
            occasion=["commute", "casual", "date"], visibility="private",
        ),
        create(
            "user_a", "gray-lounge-set.png", name="浅灰棉质家居套装", category="other",
            color="浅灰", colors=["浅灰"], warmth=2, material="棉质", pattern="纯色",
            season=["spring", "summer", "autumn"], style=["casual", "minimal"],
            occasion=["casual"], visibility="private",
        ),
    ]
    for item in (items[2], items[5]):
        response = client.patch(
            f"/api/v1/items/{item['id']}", headers=auth("user_a"), json={"is_favorite": True}
        )
        response.raise_for_status()

    pending_file = upload("user_a", "denim-overshirt.png")
    pending = client.post(
        "/api/v1/ai/recognize", headers=auth("user_a"), json={"imageFileId": pending_file}
    ).json()["data"]
    client.patch(
        f"/api/v1/items/{pending['id']}", headers=auth("user_a"),
        json={
            "name": "水洗蓝牛仔衬衫（待确认）", "category": "tops", "color": "水洗蓝",
            "colors": ["水洗蓝"], "warmth": 2, "material": "牛仔布", "pattern": "纯色",
            "season": ["spring", "autumn"], "style": ["street", "casual"],
            "occasion": ["casual", "travel"], "visibility": "private",
        },
    ).raise_for_status()

    settings.wardrobe_ai_provider = "disabled"
    failed_file = upload("user_a", "khaki-trench.png")
    failed_response = client.post(
        "/api/v1/ai/recognize", headers=auth("user_a"), json={"imageFileId": failed_file}
    )
    if failed_response.status_code != 503:
        raise RuntimeError("没有生成预期的 AI 失败演示记录")
    failed = next(
        item for item in client.get("/api/v1/items?page=1&pageSize=100", headers=auth("user_a")).json()["data"]["list"]
        if item["verify_status"] == "failed"
    )
    client.patch(
        f"/api/v1/items/{failed['id']}", headers=auth("user_a"),
        json={"name": "AI 识别失败测试（点击重试识别）"},
    ).raise_for_status()
    settings.wardrobe_ai_provider = "mock"

    public_item = create(
        "user_b", "khaki-trench.png", name="卡其色经典风衣", category="outerwear",
        color="卡其", colors=["卡其"], warmth=3, material="棉质斜纹布", pattern="纯色",
        season=["spring", "autumn"], style=["vintage", "minimal"],
        occasion=["travel", "commute", "date"], visibility="public",
    )
    wish_response = client.post(
        "/api/v1/wish-items", headers=auth("user_a"), json={"source_item_id": public_item["id"]}
    )
    wish_response.raise_for_status()
    client.close()
    return {
        "user_a_items": 10,
        "user_b_items": 1,
        "categories": 8,
        "pending": pending["id"],
        "failed": failed["id"],
        "public_item": public_item["id"],
        "wish": wish_response.json()["data"]["id"],
    }


if __name__ == "__main__":
    backup = back_up_and_clear()
    summary = seed_demo()
    print(f"backup={backup}")
    print(summary)
