import os
from pathlib import Path

from dotenv import load_dotenv

# .env 파일 로드 (TEST_FCM_TOKEN 등을 위해)
load_dotenv()

# database.py import 전에 환경변수 설정 (모듈 레벨 엔진 생성을 위해 필요)
os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost/dummy")
os.environ.setdefault("GEMINI_API_KEY", "dummy")

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.services.fcm_sender import initialize_firebase  # noqa: E402
from app.services.oauth2 import TokenVerificationError  # noqa: E402


# Firebase 초기화 (테스트 시작 시 한 번만)
@pytest.fixture(scope="session", autouse=True)
def initialize_firebase_for_tests():
    """테스트 세션 시작 시 Firebase 초기화"""
    initialize_firebase()
    yield


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
    async_url = _to_asyncpg_url(database_url)

    engine = create_async_engine(async_url, echo=False, pool_pre_ping=True)
    await _init_schema(database_url)

    yield engine

    await engine.dispose()


def _to_asyncpg_url(database_url: str) -> str:
    return database_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    ).replace("postgresql://", "postgresql+asyncpg://")


async def _init_schema(database_url: str) -> None:
    """init-db.sql로 스키마 생성 (partial unique index, trigger 포함)"""
    init_sql = (Path(__file__).parent.parent / "scripts" / "init-db.sql").read_text()
    raw_url = database_url.replace("postgresql+psycopg2://", "postgresql://")
    conn = await asyncpg.connect(raw_url)
    try:
        await conn.execute(init_sql)
    finally:
        await conn.close()


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
async def test_user(test_db_session: AsyncSession):
    """기본 테스트 사용자 생성 fixture"""
    from app.models.user import User
    from tests.fixtures.auth_fixtures import create_test_user_data

    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()
    return user


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

    monkeypatch.setattr("app.services.oauth2.verify_apple_token", mock_verify)


@pytest.fixture
def mock_verify_apple_token_failure(monkeypatch):
    """Apple token 검증 실패 Mock"""

    async def mock_verify(id_token: str, **kwargs):
        raise TokenVerificationError("Invalid token signature")

    monkeypatch.setattr("app.services.oauth2.verify_apple_token", mock_verify)


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

    monkeypatch.setattr("app.services.oauth2.verify_google_token", mock_verify)


@pytest.fixture
def mock_verify_google_token_failure(monkeypatch):
    """Google token 검증 실패 Mock"""

    async def mock_verify(id_token: str, **kwargs):
        raise TokenVerificationError("Invalid Google token")

    monkeypatch.setattr("app.services.oauth2.verify_google_token", mock_verify)
