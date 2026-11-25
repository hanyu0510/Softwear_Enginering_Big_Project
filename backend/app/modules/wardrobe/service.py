from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.modules.wardrobe.ai import Recognition, get_recognizer
from app.modules.wardrobe.models import Item, UploadedFile, WishItem
from app.modules.wardrobe.schemas import (
    Category,
    ItemCreate,
    ItemPatch,
    Occasion,
    Season,
    Style,
)
from app.modules.wardrobe.storage import clone_image


def media_url(file_id: str | None, variant: str = "original") -> str | None:
    if not file_id:
        return None
    suffix = "?variant=thumb" if variant == "thumb" else ""
    return f"/api/v1/uploads/{file_id}{suffix}"


def item_to_dict(item: Item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "imageFileId": item.image_file_id,
        "image_url": media_url(item.image_file_id),
        "thumb_url": media_url(item.image_file_id, "thumb"),
        "category": item.category,
        "color": item.color,
        "colors": item.colors or [],
        "warmth": item.warmth,
        "material": item.material,
        "pattern": item.pattern,
        "season": item.season or [],
        "style": item.style or [],
        "occasion": item.occasion or [],
        "visibility": item.visibility,
        "source": item.source,
        "confidence": item.confidence,
        "verify_status": item.verify_status,
        "is_favorite": item.is_favorite,
        "low_confidence_fields": item.low_confidence_fields or [],
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _get_owned_item(db: Session, item_id: str, user_id: str) -> Item:
    item = db.scalar(
        select(Item).where(
            Item.id == item_id,
            Item.user_id == user_id,
            Item.deleted_at.is_(None),
        )
    )
    if item is None:
        raise ApiError(40401, "衣物不存在或不可见", 404)
    return item


def get_item(db: Session, item_id: str, user_id: str) -> Item:
    item = db.scalar(select(Item).where(Item.id == item_id, Item.deleted_at.is_(None)))
    if item is None:
        raise ApiError(40401, "衣物不存在或不可见", 404)
    if item.user_id != user_id and (
        item.visibility != "public" or item.verify_status != "confirmed"
    ):
        raise ApiError(40401, "衣物不存在或不可见", 404)
    return item


def list_items(
    db: Session,
    user_id: str,
    category: str | None,
    season: str | None,
    color: str | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Item], int]:
    conditions = [Item.user_id == user_id, Item.deleted_at.is_(None)]
    if category:
        conditions.append(Item.category == category)
    if color:
        conditions.append(Item.color.contains(color))
    if keyword:
        escaped = keyword.replace("%", r"\%").replace("_", r"\_")
        conditions.append(
            or_(
                Item.name.ilike(f"%{escaped}%", escape="\\"),
                Item.color.ilike(f"%{escaped}%", escape="\\"),
            )
        )

    records = list(
        db.scalars(select(Item).where(*conditions).order_by(Item.created_at.desc(), Item.id.desc()))
    )
    if season:
        records = [item for item in records if season in (item.season or [])]
    total = len(records)
    start = (page - 1) * page_size
    return records[start : start + page_size], total


def _claim_file(db: Session, file_id: str, user_id: str, item_id: str) -> UploadedFile:
    stored_file = db.scalar(select(UploadedFile).where(UploadedFile.id == file_id))
    if stored_file is None or stored_file.owner_id != user_id:
        raise ApiError(40401, "图片文件不存在或不属于当前用户", 404)
    if stored_file.linked_item_id:
        linked_item = db.get(Item, stored_file.linked_item_id)
        may_reuse_failed_upload = bool(
            linked_item
            and linked_item.user_id == user_id
            and (linked_item.verify_status == "failed" or linked_item.deleted_at is not None)
        )
        if not may_reuse_failed_upload:
            raise ApiError(40901, "图片文件已关联其他衣物", 409)
        if linked_item.deleted_at is None:
            linked_item.deleted_at = datetime.now(timezone.utc)
    stored_file.linked_item_id = item_id
    return stored_file


def create_manual_item(db: Session, user_id: str, payload: ItemCreate) -> Item:
    item_id = f"item_{uuid4().hex}"
    _claim_file(db, payload.image_file_id, user_id, item_id)
    data = payload.model_dump(by_alias=False)
    image_file_id = data.pop("image_file_id")
    item = Item(
        id=item_id,
        user_id=user_id,
        image_file_id=image_file_id,
        source="manual",
        confidence=1.0,
        verify_status="confirmed",
        low_confidence_fields=[],
        **data,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item_id: str, user_id: str, payload: ItemPatch) -> Item:
    item = _get_owned_item(db, item_id, user_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item_id: str, user_id: str) -> None:
    item = _get_owned_item(db, item_id, user_id)
    item.deleted_at = datetime.now(timezone.utc)
    db.commit()


def confirm_item(db: Session, item_id: str, user_id: str) -> Item:
    item = _get_owned_item(db, item_id, user_id)
    if item.verify_status != "pending":
        raise ApiError(40901, "只有待确认衣物可以确认", 409)
    if not item.category:
        raise ApiError(40001, "确认前必须补充衣物类别", 400)
    item.verify_status = "confirmed"
    db.commit()
    db.refresh(item)
    return item


def _validate_recognition(result: Recognition) -> None:
    try:
        if result.category is not None:
            Category(result.category)
        for value in result.season:
            Season(value)
        for value in result.style:
            Style(value)
        for value in result.occasion:
            Occasion(value)
        if result.warmth is not None and not 1 <= result.warmth <= 5:
            raise ValueError("warmth")
        if not 0 <= result.confidence <= 1:
            raise ValueError("confidence")
    except ValueError as exc:
        raise ApiError(50002, "AI 返回了不符合公约的字段", 503) from exc


def _apply_recognition(item: Item, result: Recognition) -> None:
    _validate_recognition(result)
    item.category = result.category
    item.color = result.color
    item.warmth = result.warmth
    item.material = result.material
    item.pattern = result.pattern
    item.season = result.season
    item.style = result.style
    item.occasion = result.occasion
    item.confidence = result.confidence
    item.low_confidence_fields = result.low_confidence_fields
    item.verify_status = "pending"


def recognize_image(
    db: Session, user_id: str, file_id: str, settings: Settings
) -> Item:
    item_id = f"item_{uuid4().hex}"
    stored_file = _claim_file(db, file_id, user_id, item_id)
    item = Item(
        id=item_id,
        user_id=user_id,
        name="待确认衣物",
        image_file_id=file_id,
        source="ai",
        confidence=0,
        verify_status="recognizing",
    )
    db.add(item)
    db.commit()
    try:
        result = get_recognizer(settings).recognize(stored_file.stored_path)
        _apply_recognition(item, result)
        db.commit()
        db.refresh(item)
        return item
    except ApiError:
        item.verify_status = "failed"
        db.commit()
        raise


def retry_recognition(db: Session, item_id: str, user_id: str, settings: Settings) -> Item:
    item = _get_owned_item(db, item_id, user_id)
    if item.verify_status != "failed":
        raise ApiError(40901, "只有识别失败的衣物可以重试", 409)
    stored_file = db.get(UploadedFile, item.image_file_id)
    if stored_file is None or not Path(stored_file.stored_path).is_file():
        raise ApiError(40401, "关联图片已不可用", 404)
    item.verify_status = "recognizing"
    db.commit()
    try:
        result = get_recognizer(settings).recognize(stored_file.stored_path)
        _apply_recognition(item, result)
        db.commit()
        db.refresh(item)
        return item
    except ApiError:
        item.verify_status = "failed"
        db.commit()
        raise


def create_wish(db: Session, user_id: str, source_item_id: str) -> WishItem:
    source = db.scalar(
        select(Item).where(
            Item.id == source_item_id,
            Item.deleted_at.is_(None),
            Item.visibility == "public",
            Item.verify_status == "confirmed",
        )
    )
    if source is None or source.user_id == user_id:
        raise ApiError(40401, "只能收藏其他用户当前公开的单品", 404)
    snapshot = {
        "name": source.name,
        "image_url": media_url(source.image_file_id),
        "thumb_url": media_url(source.image_file_id, "thumb"),
        "category": source.category,
        "color": source.color,
        "warmth": source.warmth,
        "season": source.season or [],
        "style": source.style or [],
        "occasion": source.occasion or [],
    }
    wish = WishItem(
        id=f"wish_{uuid4().hex}",
        user_id=user_id,
        source_item_id=source.id,
        snapshot=snapshot,
    )
    db.add(wish)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(40901, "该单品已在心愿衣橱中", 409) from exc
    db.refresh(wish)
    return wish


def wish_to_dict(db: Session, wish: WishItem) -> dict:
    source = db.scalar(select(Item).where(Item.id == wish.source_item_id))
    available = bool(
        source
        and source.deleted_at is None
        and source.visibility == "public"
        and source.verify_status == "confirmed"
    )
    snapshot = dict(wish.snapshot)
    if not available:
        snapshot["image_url"] = None
        snapshot["thumb_url"] = None
    return {
        "id": wish.id,
        "source_item_id": wish.source_item_id,
        "snapshot": snapshot,
        "available": available,
        "created_at": wish.created_at.isoformat(),
    }


def list_wishes(db: Session, user_id: str) -> list[WishItem]:
    return list(
        db.scalars(
            select(WishItem)
            .where(WishItem.user_id == user_id)
            .order_by(WishItem.created_at.desc())
        )
    )


def delete_wish(db: Session, wish_id: str, user_id: str) -> None:
    wish = db.scalar(
        select(WishItem).where(WishItem.id == wish_id, WishItem.user_id == user_id)
    )
    if wish is None:
        raise ApiError(40401, "心愿记录不存在", 404)
    db.delete(wish)
    db.commit()


def copy_wish_to_wardrobe(
    db: Session, wish_id: str, user_id: str, settings: Settings
) -> Item:
    wish = db.scalar(
        select(WishItem).where(WishItem.id == wish_id, WishItem.user_id == user_id)
    )
    if wish is None:
        raise ApiError(40401, "心愿记录不存在", 404)
    source = db.scalar(
        select(Item).where(
            Item.id == wish.source_item_id,
            Item.deleted_at.is_(None),
            Item.visibility == "public",
            Item.verify_status == "confirmed",
        )
    )
    if source is None:
        raise ApiError(40901, "来源单品已不可用，不能复制", 409)
    source_file = db.get(UploadedFile, source.image_file_id)
    if source_file is None:
        raise ApiError(40401, "来源图片已不可用", 404)
    new_file = clone_image(source_file, user_id, settings)
    item_id = f"item_{uuid4().hex}"
    new_file.linked_item_id = item_id
    item = Item(
        id=item_id,
        user_id=user_id,
        name=source.name,
        image_file_id=new_file.id,
        category=source.category,
        color=source.color,
        colors=list(source.colors or []),
        warmth=source.warmth,
        material=source.material,
        pattern=source.pattern,
        season=list(source.season or []),
        style=list(source.style or []),
        occasion=list(source.occasion or []),
        visibility="private",
        source="manual",
        confidence=1,
        verify_status="confirmed",
    )
    db.add_all([new_file, item])
    db.commit()
    db.refresh(item)
    return item


def list_recommendation_candidates(db: Session, user_id: str, scope: str) -> list[dict]:
    if scope not in {"owned", "owned_and_wish"}:
        raise ValueError("scope must be owned or owned_and_wish")
    owned = list(
        db.scalars(
            select(Item).where(
                Item.user_id == user_id,
                Item.deleted_at.is_(None),
                Item.verify_status == "confirmed",
            )
        )
    )
    candidates = [
        {
            "source": "owned",
            "id": item.id,
            "name": item.name,
            "imageUrl": media_url(item.image_file_id),
            "category": item.category,
            "color": item.color,
            "warmth": item.warmth,
            "season": item.season or [],
            "style": item.style or [],
            "occasion": item.occasion or [],
            "available": True,
        }
        for item in owned
    ]
    if scope == "owned_and_wish":
        for wish in list_wishes(db, user_id):
            payload = wish_to_dict(db, wish)
            if payload["available"]:
                snapshot = payload["snapshot"]
                candidates.append(
                    {
                        "source": "wish",
                        "id": wish.id,
                        "name": snapshot["name"],
                        "imageUrl": snapshot["image_url"],
                        "category": snapshot.get("category"),
                        "color": snapshot.get("color"),
                        "warmth": snapshot.get("warmth"),
                        "season": snapshot.get("season", []),
                        "style": snapshot.get("style", []),
                        "occasion": snapshot.get("occasion", []),
                        "available": True,
                    }
                )
    return candidates
