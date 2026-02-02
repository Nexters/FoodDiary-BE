from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

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


async def _execute_init_sql(conn) -> None:
    """init-db.sql 파일 실행"""
    from pathlib import Path

    import aiofiles

    sql_file_path = Path(__file__).parent.parent.parent / "scripts" / "init-db.sql"
    if not sql_file_path.exists():
        return

    async with aiofiles.open(sql_file_path, encoding="utf-8") as f:
        init_sql = await f.read()

    # asyncpg를 직접 사용하여 전체 SQL 파일 실행
    # (함수, DO 블록, 트리거 등 복잡한 구문 처리)
    raw_conn = await conn.get_raw_connection()
    try:
        await raw_conn.driver_connection.execute(init_sql)
        print("✅ init-db.sql executed")
    except Exception as e:
        if "already exists" not in str(e):
            print(f"⚠️  init-db.sql execution warning: {e}")


async def create_tables() -> None:
    """init-db.sql 실행 및 자동 마이그레이션 (비동기)"""
    from app.core.auto_migrations import run_auto_migrations

    async with engine.begin() as conn:
        # 1. init-db.sql 실행
        await _execute_init_sql(conn)

        # 2. 자동 마이그레이션 실행 (init-db.sql과 실제 스키마 차이 감지)
        await run_auto_migrations(conn)
