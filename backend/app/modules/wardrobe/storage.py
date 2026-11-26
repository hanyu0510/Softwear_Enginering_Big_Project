from io import BytesIO
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings
from app.core.errors import ApiError
from app.modules.wardrobe.models import UploadedFile


FORMAT_INFO = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}


async def persist_image(upload: UploadFile, owner_id: str, settings: Settings) -> UploadedFile:
    data = await upload.read(settings.max_image_bytes + 1)
    if len(data) > settings.max_image_bytes:
        raise ApiError(41301, "图片超过大小限制", 413)
    if not data:
        raise ApiError(40001, "图片内容为空", 400)

    try:
        image = Image.open(BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ApiError(40001, "文件不是有效图片", 400) from exc

    if image.format not in FORMAT_INFO:
        raise ApiError(40001, "仅支持 JPEG、PNG、WEBP 图片", 400)

    extension, mime_type = FORMAT_INFO[image.format]
    file_id = f"file_{uuid4().hex}"
    owner_dir = settings.upload_dir.resolve() / owner_id
    owner_dir.mkdir(parents=True, exist_ok=True)
    original_path = owner_dir / f"{file_id}.{extension}"
    thumb_path = owner_dir / f"{file_id}_thumb.jpg"

    save_image = image
    if image.format == "JPEG" and image.mode not in ("RGB", "L"):
        save_image = image.convert("RGB")
    save_image.save(original_path, format=image.format)

    has_alpha = image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )
    if has_alpha:
        rgba = image.convert("RGBA")
        thumbnail = Image.new("RGB", rgba.size, "white")
        thumbnail.paste(rgba, mask=rgba.getchannel("A"))
    else:
        thumbnail = image.convert("RGB")
    thumbnail.thumbnail((480, 480))
    thumbnail.save(thumb_path, format="JPEG", quality=85, optimize=True)

    return UploadedFile(
        id=file_id,
        owner_id=owner_id,
        original_name=(upload.filename or "upload")[:255],
        mime_type=mime_type,
        stored_path=str(original_path),
        thumb_path=str(thumb_path),
        size=original_path.stat().st_size,
    )


def clone_image(source: UploadedFile, new_owner_id: str, settings: Settings) -> UploadedFile:
    source_path = Path(source.stored_path)
    source_thumb = Path(source.thumb_path)
    if not source_path.is_file() or not source_thumb.is_file():
        raise ApiError(40401, "来源图片已不可用", 404)

    extension = source_path.suffix.lower() or ".jpg"
    file_id = f"file_{uuid4().hex}"
    owner_dir = settings.upload_dir.resolve() / new_owner_id
    owner_dir.mkdir(parents=True, exist_ok=True)
    target_path = owner_dir / f"{file_id}{extension}"
    target_thumb = owner_dir / f"{file_id}_thumb.jpg"
    copy2(source_path, target_path)
    copy2(source_thumb, target_thumb)
    return UploadedFile(
        id=file_id,
        owner_id=new_owner_id,
        original_name=source.original_name,
        mime_type=source.mime_type,
        stored_path=str(target_path),
        thumb_path=str(target_thumb),
        size=target_path.stat().st_size,
    )
