"""Single registration point for every business module router."""

from fastapi import APIRouter

from app.modules.wardrobe.router import router as wardrobe_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(wardrobe_router)
