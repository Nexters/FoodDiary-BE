import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import create_tables
from app.core.scheduler import start_scheduler
from app.routers import (
    auth_router,
    device_router,
    diaries_router,
    health_router,
    insights_router,
    photos_router,
    restaurant_router,
    users_router,
)
from app.services.fcm_sender import initialize_firebase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 시 초기화"""
    await create_tables()
    initialize_firebase()
    scheduler_task = start_scheduler()
    yield
    scheduler_task.cancel()
    with suppress(asyncio.CancelledError):
        await scheduler_task


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="음식 사진 기반 기록 서비스 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(device_router)
app.include_router(diaries_router)
app.include_router(insights_router)
app.include_router(photos_router)
app.include_router(restaurant_router)
app.include_router(users_router)
