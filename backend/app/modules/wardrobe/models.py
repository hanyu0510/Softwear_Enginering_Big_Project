from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(64))
    stored_path: Mapped[str] = mapped_column(Text)
    thumb_path: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(Integer)
    linked_item_id: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(120))
    image_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("uploaded_files.id"), nullable=True, index=True
    )
    category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    colors: Mapped[list] = mapped_column(JSON, default=list)
    warmth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    material: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pattern: Mapped[str | None] = mapped_column(String(80), nullable=True)
    season: Mapped[list] = mapped_column(JSON, default=list)
    style: Mapped[list] = mapped_column(JSON, default=list)
    occasion: Mapped[list] = mapped_column(JSON, default=list)
    visibility: Mapped[str] = mapped_column(String(16), default="private", index=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    verify_status: Mapped[str] = mapped_column(String(20), default="confirmed", index=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    low_confidence_fields: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WishItem(Base):
    __tablename__ = "wish_items"
    __table_args__ = (UniqueConstraint("user_id", "source_item_id", name="uq_wish_owner_source"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    source_item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
