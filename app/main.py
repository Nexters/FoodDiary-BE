from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import create_tables
from app.routers import auth_router, health_router, insights_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 시 테이블 생성"""
    await create_tables()
    yield


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
app.include_router(insights_router)
