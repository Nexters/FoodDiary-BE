import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

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


def _parse_sql_statements(sql_content: str) -> list[str]:
    """SQL 파일을 실행 가능한 구문 리스트로 파싱"""
    statements = []
    current_stmt = []
    in_function = False
    in_do_block = False

    for line in sql_content.split("\n"):
        stripped = line.strip()

        if not stripped or stripped.startswith("--"):
            continue

        upper = stripped.upper()
        if "CREATE FUNCTION" in upper or "CREATE OR REPLACE FUNCTION" in upper:
            in_function = True
        if upper.startswith("DO $$"):
            in_do_block = True

        current_stmt.append(line)

        if stripped.endswith(";"):
            if in_function and "$$;" in stripped:
                in_function = False
            elif in_do_block and "END $$;" in stripped:
                in_do_block = False

            if not in_function and not in_do_block:
                stmt = "\n".join(current_stmt).strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []

    return statements


def _is_expected_error(e: Exception) -> bool:
    """예상된 에러인지 판단 (already exists 등)"""
    error_msg = str(e).lower()
    expected_patterns = ["already exists", "duplicate"]
    return any(pattern in error_msg for pattern in expected_patterns)


async def _execute_init_sql(conn) -> None:
    """init-db.sql 파일을 구문별로 실행하고 상세 로깅"""
    from pathlib import Path

    import aiofiles

    sql_file_path = Path(__file__).parent.parent.parent / "scripts" / "init-db.sql"
    if not sql_file_path.exists():
        logger.warning("init-db.sql not found, skipping initialization")
        return

    async with aiofiles.open(sql_file_path, encoding="utf-8") as f:
        init_sql = await f.read()

    statements = _parse_sql_statements(init_sql)
    raw_conn = await conn.get_raw_connection()
    error_count = 0

    for i, stmt in enumerate(statements, 1):
        try:
            await raw_conn.driver_connection.execute(stmt)
        except Exception as e:
            if not _is_expected_error(e):
                stmt_preview = stmt[:60].replace("\n", " ")
                logger.error(f"[{i}/{len(statements)}] Failed: {stmt_preview}...")
                logger.error(f"  Error: {e}")
                error_count += 1

    if error_count == 0:
        logger.info("✅ init-db.sql executed successfully")


async def create_tables() -> None:
    """init-db.sql 실행 및 자동 마이그레이션 (비동기)"""
    from app.core.auto_migrations import run_auto_migrations

    async with engine.begin() as conn:
        await _execute_init_sql(conn)

    async with engine.begin() as conn:
        await run_auto_migrations(conn)
