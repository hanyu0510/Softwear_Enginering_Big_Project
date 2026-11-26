from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUserId
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.errors import ApiError, success
from app.modules.wardrobe.models import Item, UploadedFile
from app.modules.wardrobe.schemas import (
    Category,
    ItemCreate,
    ItemPatch,
    RecognizeRequest,
    Season,
    WishCreate,
)
from app.modules.wardrobe.service import (
    confirm_item,
    copy_wish_to_wardrobe,
    create_manual_item,
    create_wish,
    delete_item,
    delete_wish,
    get_item,
    item_to_dict,
    list_items,
    list_wishes,
    recognize_image,
    retry_recognition,
    update_item,
    wish_to_dict,
)
from app.modules.wardrobe.storage import persist_image


router = APIRouter(tags=["wardrobe"])
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def recognition_payload(item: Item) -> dict:
    suggestion = {
        key: getattr(item, key)
        for key in (
            "category",
            "color",
            "warmth",
            "material",
            "pattern",
            "season",
            "style",
            "occasion",
        )
    }
    return {
        "id": item.id,
        "image_url": f"/api/v1/uploads/{item.image_file_id}",
        "thumb_url": f"/api/v1/uploads/{item.image_file_id}?variant=thumb",
        "verify_status": item.verify_status,
        "suggestion": suggestion,
        "confidence": item.confidence,
        "low_confidence_fields": item.low_confidence_fields or [],
    }


@router.post("/uploads/image")
async def upload_image(
    request: Request,
    user_id: CurrentUserId,
    db: DbSession,
    settings: AppSettings,
    file: UploadFile = File(...),
):
    stored_file = await persist_image(file, user_id, settings)
    db.add(stored_file)
    db.commit()
    return success(
        request,
        {
            "fileId": stored_file.id,
            "url": f"/api/v1/uploads/{stored_file.id}",
            "thumbUrl": f"/api/v1/uploads/{stored_file.id}?variant=thumb",
        },
    )


@router.get("/uploads/{file_id}")
def read_image(
    file_id: str,
    user_id: CurrentUserId,
    db: DbSession,
    variant: str = Query(default="original", pattern="^(original|thumb)$"),
):
    stored_file = db.get(UploadedFile, file_id)
    if stored_file is None:
        raise ApiError(40401, "图片不存在或不可见", 404)
    may_read_public = db.scalar(
        select(Item.id).where(
            Item.image_file_id == file_id,
            Item.visibility == "public",
            Item.verify_status == "confirmed",
            Item.deleted_at.is_(None),
        )
    )
    if stored_file.owner_id != user_id and may_read_public is None:
        raise ApiError(40401, "图片不存在或不可见", 404)
    path = Path(stored_file.thumb_path if variant == "thumb" else stored_file.stored_path)
    if not path.is_file():
        raise ApiError(40401, "图片文件已不可用", 404)
    media_type = "image/jpeg" if variant == "thumb" else stored_file.mime_type
    return FileResponse(path, media_type=media_type)


@router.get("/items")
def read_items(
    request: Request,
    user_id: CurrentUserId,
    db: DbSession,
    category: Category | None = None,
    season: Season | None = None,
    color: str | None = Query(default=None, max_length=32),
    keyword: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
):
    records, total = list_items(
        db, user_id, category, season, color, keyword, page, page_size
    )
    return success(
        request,
        {"list": [item_to_dict(item) for item in records], "total": total},
    )


@router.post("/items", status_code=201)
def create_item(
    payload: ItemCreate,
    request: Request,
    user_id: CurrentUserId,
    db: DbSession,
):
    return success(request, item_to_dict(create_manual_item(db, user_id, payload)))


@router.get("/items/{item_id}")
def read_item(
    item_id: str, request: Request, user_id: CurrentUserId, db: DbSession
):
    item = get_item(db, item_id, user_id)
    payload = item_to_dict(item)
    if item.user_id != user_id:
        payload["is_favorite"] = False
    return success(request, payload)


@router.patch("/items/{item_id}")
def patch_item(
    item_id: str,
    payload: ItemPatch,
    request: Request,
    user_id: CurrentUserId,
    db: DbSession,
):
    if "name" in payload.model_fields_set and payload.name is None:
        raise ApiError(40001, "name 不能为 null", 400)
    item = update_item(db, item_id, user_id, payload)
    return success(request, item_to_dict(item))


@router.delete("/items/{item_id}")
def remove_item(
    item_id: str, request: Request, user_id: CurrentUserId, db: DbSession
):
    delete_item(db, item_id, user_id)
    return success(request, None)


@router.post("/items/{item_id}/confirm")
def confirm(
    item_id: str, request: Request, user_id: CurrentUserId, db: DbSession
):
    return success(request, item_to_dict(confirm_item(db, item_id, user_id)))


@router.post("/ai/recognize")
def recognize(
    payload: RecognizeRequest,
    request: Request,
    user_id: CurrentUserId,
    db: DbSession,
    settings: AppSettings,
):
    item = recognize_image(db, user_id, payload.image_file_id, settings)
    return success(request, recognition_payload(item))


@router.post("/ai/retry/{item_id}")
def retry(
    item_id: str,
    request: Request,
    user_id: CurrentUserId,
    db: DbSession,
    settings: AppSettings,
):
    item = retry_recognition(db, item_id, user_id, settings)
    return success(request, recognition_payload(item))


@router.get("/wish-items")
def read_wishes(
    request: Request, user_id: CurrentUserId, db: DbSession
):
    records = list_wishes(db, user_id)
    return success(
        request,
        {"list": [wish_to_dict(db, wish) for wish in records], "total": len(records)},
    )


@router.post("/wish-items", status_code=201)
def add_wish(
    payload: WishCreate,
    request: Request,
    user_id: CurrentUserId,
    db: DbSession,
):
    wish = create_wish(db, user_id, payload.source_item_id)
    return success(request, wish_to_dict(db, wish))


@router.delete("/wish-items/{wish_id}")
def remove_wish(
    wish_id: str, request: Request, user_id: CurrentUserId, db: DbSession
):
    delete_wish(db, wish_id, user_id)
    return success(request, None)


@router.post("/wish-items/{wish_id}/copy-to-wardrobe", status_code=201)
def copy_wish(
    wish_id: str,
    request: Request,
    user_id: CurrentUserId,
    db: DbSession,
    settings: AppSettings,
):
    item = copy_wish_to_wardrobe(db, wish_id, user_id, settings)
    return success(request, item_to_dict(item))
