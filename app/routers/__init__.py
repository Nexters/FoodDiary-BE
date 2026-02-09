from app.routers.auth import router as auth_router
from app.routers.device import router as device_router
from app.routers.health import router as health_router
from app.routers.insights import router as insights_router
from app.routers.photos import router as photos_router

__all__ = [
    "auth_router",
    "device_router",
    "health_router",
    "insights_router",
    "photos_router",
]
