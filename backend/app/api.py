"""Single registration point for every business module router."""

from fastapi import APIRouter

from app.modules.community.router_fastapi import router as community_router
from app.modules.wardrobe.router import router as wardrobe_router


api_router = APIRouter(prefix="/api/v1")
community_router.routes[:] = [route for route in community_router.routes
    if not (route.path == "/users/{user_id}/follow")]
api_router.include_router(community_router)
api_router.include_router(wardrobe_router)
