from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.base import Base

# 비동기 SQLAlchemy 엔진 생성
# PostgreSQL URL을 asyncpg 드라이버로 변환
async_database_url = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

engine = create_async_engine(
    async_database_url,
    echo=settings.DEBUG,  # DEBUG 모드일 때만 SQL 쿼리 로그 출력
    pool_pre_ping=True,  # 연결 전 ping으로 연결 상태 확인
)

# 비동기 세션 팩토리 생성
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    비동기 데이터베이스 세션을 생성하고 반환하는 의존성 함수
    FastAPI의 Depends에서 사용
    """
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables() -> None:
    """모든 테이블 생성 (비동기)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
