import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

# database.py import 전에 환경변수 설정 (모듈 레벨 엔진 생성을 위해 필요)
os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost/dummy")

from app.core.config import Settings
from app.core.database import get_session
from app.main import app
from app.models.base import Base
from app.services.auth import TokenVerificationError


@pytest.fixture(scope="session")
def test_settings():
    """테스트용 Settings 오버라이드"""
    return Settings(
        PROJECT_NAME="FoodDiary Test",
        DEBUG=True,
        DATABASE_URL="",  # Will be set by postgres_container
        KAKAO_REST_API_KEY="test_kakao_key",
        GEMINI_API_KEY="test_gemini_key",
        APPLE_CLIENT_ID="test.client.id",
        APPLE_JWK_URL="https://appleid.apple.com/auth/keys",
        APPLE_BASE_URL="https://appleid.apple.com",
        JWT_SECRET_KEY="test_secret_key_for_testing_only",
        JWT_ALGORITHM="HS256",
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES=0,
    )


@pytest.fixture
def postgres_container():
    """PostgreSQL TestContainer (function-scoped)"""
    with PostgresContainer(
        "postgres:16-alpine",
        username="test_user",
        password="test_pass",
        dbname="test_fooddiary",
    ) as postgres:
        yield postgres


@pytest_asyncio.fixture
async def test_db_engine(postgres_container) -> AsyncEngine:
    """비동기 테스트 DB 엔진 생성"""
    database_url = postgres_container.get_connection_url()
    # psycopg2 driver를 asyncpg로 변경
    async_url = database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        async_url,
        echo=False,
        pool_pre_ping=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_db_engine: AsyncEngine):
    """각 테스트마다 격리된 DB 세션 (function-scoped)"""
    session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        yield session

    # Cleanup: 테스트 후 모든 데이터 삭제
    async with test_db_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def test_client(test_db_session: AsyncSession, test_settings, monkeypatch):
    """FastAPI TestClient with overridden dependencies"""
    from httpx import ASGITransport, AsyncClient

    # Override settings
    monkeypatch.setattr("app.core.config.settings", test_settings)

    # Override get_session dependency
    async def override_get_session():
        yield test_db_session

    app.dependency_overrides[get_session] = override_get_session

    # Create async client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def mock_verify_apple_token_success(monkeypatch):
    """Apple token 검증 성공 Mock"""

    async def mock_verify(id_token: str, **kwargs):
        # Return mock claims based on token
        return {
            "sub": "apple_user_123",
            "email": "test@apple.com",
            "iss": "https://appleid.apple.com",
            "aud": "test.client.id",
            "exp": 9999999999,
            "iat": 1234567890,
        }

    monkeypatch.setattr("app.services.auth.verify_apple_token", mock_verify)


@pytest.fixture
def mock_verify_apple_token_failure(monkeypatch):
    """Apple token 검증 실패 Mock"""

    async def mock_verify(id_token: str, **kwargs):
        raise TokenVerificationError("Invalid token signature")

    monkeypatch.setattr("app.services.auth.verify_apple_token", mock_verify)


@pytest.fixture
def mock_verify_google_token_success(monkeypatch):
    """Google token 검증 성공 Mock"""

    async def mock_verify(id_token: str, **kwargs):
        # Return mock claims based on token
        return {
            "sub": "google_user_456",
            "email": "test@gmail.com",
            "iss": "https://accounts.google.com",
            "aud": "test-google-client-id.apps.googleusercontent.com",
            "exp": 9999999999,
            "iat": 1234567890,
            "email_verified": True,
        }

    monkeypatch.setattr("app.services.auth.verify_google_token", mock_verify)


@pytest.fixture
def mock_verify_google_token_failure(monkeypatch):
    """Google token 검증 실패 Mock"""

    async def mock_verify(id_token: str, **kwargs):
        raise TokenVerificationError("Invalid Google token")

    monkeypatch.setattr("app.services.auth.verify_google_token", mock_verify)
