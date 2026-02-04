"""init-db.sql과 실제 DB 스키마를 비교하여 자동 마이그레이션을 수행하는 모듈"""

from pathlib import Path

import aiofiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def _parse_init_sql_tables(sql_content: str) -> dict[str, dict]:
    """
    init-db.sql에서 테이블 정의 파싱

    Args:
        sql_content: SQL 파일 내용

    Returns:
        {
            "table_name": {
                "columns": ["col1", "col2", ...],
                "column_types": {"col1": "VARCHAR(50)", ...}
            }
        }
    """
    tables: dict[str, dict] = {}
    lines = sql_content.split("\n")
    current_table: str | None = None
    in_create_table = False

    for line in lines:
        line = line.strip()

        if line.startswith("CREATE TABLE IF NOT EXISTS"):
            current_table, in_create_table = _handle_create_table(line, tables)
            continue

        if in_create_table and line.startswith(");"):
            in_create_table = False
            current_table = None
            continue

        if _should_process_column(line, in_create_table, current_table):
            _add_column_to_table(line, tables, current_table)

    return tables


def _handle_create_table(line: str, tables: dict[str, dict]) -> tuple[str, bool]:
    """CREATE TABLE 라인 처리"""
    table_name = line.split()[5].replace("(", "").strip()
    tables[table_name] = {"columns": [], "column_types": {}}
    return table_name, True


def _should_process_column(
    line: str, in_create_table: bool, current_table: str | None
) -> bool:
    """컬럼 처리 여부 확인"""
    return (
        in_create_table
        and current_table
        and line
        and not line.startswith("--")
        and not _should_skip_line(line)
    )


def _add_column_to_table(line: str, tables: dict[str, dict], table_name: str) -> None:
    """테이블에 컬럼 추가"""
    col_name, col_type = _parse_column_definition(line)
    if col_name and col_type:
        tables[table_name]["columns"].append(col_name)
        tables[table_name]["column_types"][col_name] = col_type


def _should_skip_line(line: str) -> bool:
    """컬럼 정의가 아닌 라인인지 확인"""
    skip_keywords = ["CONSTRAINT", "PRIMARY KEY", "FOREIGN KEY", "UNIQUE"]
    return any(keyword in line.upper() for keyword in skip_keywords)


def _parse_column_definition(line: str) -> tuple[str | None, str | None]:
    """
    컬럼 정의 라인에서 컬럼명과 타입 추출

    Args:
        line: SQL 라인 (예: "id SERIAL PRIMARY KEY,")

    Returns:
        (column_name, column_type) 또는 (None, None)
    """
    parts = line.split()
    if len(parts) < 2:
        return None, None

    col_name = parts[0].strip(",")
    col_type = parts[1].strip(",")

    # 타입에 괄호가 있으면 추출 (예: VARCHAR(50))
    if "(" in col_type:
        base_type = col_type.split("(")[0]
        length = col_type.split("(")[1].split(")")[0]
        col_type = f"{base_type}({length})"

    return col_name, col_type


async def _get_current_schema(conn: AsyncConnection) -> dict[str, dict]:
    """
    실제 DB의 현재 스키마 조회

    Args:
        conn: 비동기 DB 연결

    Returns:
        {
            "table_name": {
                "columns": ["col1", "col2", ...],
                "column_types": {"col1": "character varying(50)", ...}
            }
        }
    """
    query = text(
        """
        SELECT
            table_name,
            column_name,
            data_type,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """
    )

    result = await conn.execute(query)
    rows = result.fetchall()

    tables: dict[str, dict] = {}
    for row in rows:
        table_name = row.table_name
        col_name = row.column_name
        data_type = row.data_type
        max_length = row.character_maximum_length

        if table_name not in tables:
            tables[table_name] = {"columns": [], "column_types": {}}

        tables[table_name]["columns"].append(col_name)

        # 타입 정규화 (길이 정보 포함)
        col_type = f"{data_type}({max_length})" if max_length else data_type
        tables[table_name]["column_types"][col_name] = col_type

    return tables


async def _load_init_sql() -> str:
    """init-db.sql 파일 로드"""
    sql_file_path = Path(__file__).parent.parent.parent / "scripts" / "init-db.sql"
    if not sql_file_path.exists():
        raise FileNotFoundError("init-db.sql not found")

    async with aiofiles.open(sql_file_path, encoding="utf-8") as f:
        return await f.read()


def _generate_alter_statements(
    target_schema: dict[str, dict], current_schema: dict[str, dict]
) -> list[str]:
    """
    스키마 차이를 비교하여 ALTER TABLE 문 생성

    Args:
        target_schema: 목표 스키마 (init-db.sql)
        current_schema: 현재 스키마 (실제 DB)

    Returns:
        실행할 ALTER TABLE SQL 리스트
    """
    alter_sqls = []

    for table_name, target_table in target_schema.items():
        if table_name not in current_schema:
            # 테이블이 없으면 스킵 (init-db.sql에서 생성됨)
            continue

        current_table = current_schema[table_name]
        target_columns = set(target_table["columns"])
        current_columns = set(current_table["columns"])

        # 추가해야 할 컬럼
        missing_columns = target_columns - current_columns

        for col_name in missing_columns:
            col_type = target_table["column_types"][col_name]
            alter_sql = (
                f"ALTER TABLE {table_name} "
                f"ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
            )
            alter_sqls.append(alter_sql)

    return alter_sqls


async def generate_schema_diff(conn: AsyncConnection) -> list[str]:
    """
    init-db.sql과 실제 DB 스키마를 비교하여 ALTER TABLE 생성

    Args:
        conn: 비동기 DB 연결

    Returns:
        실행할 ALTER TABLE SQL 리스트
    """
    try:
        # 1. init-db.sql 로드 및 파싱
        init_sql = await _load_init_sql()
        target_schema = await _parse_init_sql_tables(init_sql)

        # 2. 현재 DB 스키마 조회
        current_schema = await _get_current_schema(conn)

        # 3. 차이점 비교 및 ALTER TABLE 생성
        return _generate_alter_statements(target_schema, current_schema)

    except FileNotFoundError:
        print("⚠️  init-db.sql not found")
        return []


async def run_auto_migrations(conn: AsyncConnection) -> None:
    """
    자동으로 스키마 차이를 감지하고 마이그레이션 실행

    Args:
        conn: 비동기 DB 연결
    """
    alter_sqls = await generate_schema_diff(conn)

    if not alter_sqls:
        print("✅ Schema is up to date (no auto-migrations needed)")
        return

    print(f"🔄 Applying {len(alter_sqls)} auto-generated migrations:")
    for i, sql in enumerate(alter_sqls, start=1):
        try:
            await conn.execute(text(sql))
            print(f"  ✅ {i}. {sql}")
        except Exception as e:
            print(f"  ⚠️  {i}. Failed: {sql}")
            print(f"      Error: {e}")
