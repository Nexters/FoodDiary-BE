"""Diary 서비스 레이어"""

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Diary


async def get_or_create_diary(
    db: AsyncSession,
    user_id: UUID,
    diary_date: date,
    time_type: str,
) -> Diary:
    """
    다이어리를 조회하거나 생성합니다 (upsert).

    user_id + date + time_type 조합으로 다이어리를 찾고,
    없으면 새로 생성합니다.

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        diary_date: 일기 날짜
        time_type: 끼니 타입 ('breakfast', 'lunch', 'dinner', 'snack')

    Returns:
        Diary: 조회되거나 생성된 다이어리
    """
    # diary_date를 datetime으로 변환 (timezone aware)
    diary_datetime = datetime.combine(diary_date, datetime.min.time(), tzinfo=UTC)

    # 1. SELECT로 기존 다이어리 조회
    stmt = select(Diary).where(
        Diary.user_id == user_id,
        Diary.diary_date == diary_datetime,
        Diary.time_type == time_type,
        Diary.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    diary = result.scalar_one_or_none()

    # 2. 없으면 INSERT
    if diary is None:
        diary = Diary(
            user_id=user_id,
            diary_date=diary_datetime,
            time_type=time_type,
            photo_count=0,
            tags=[],
        )
        db.add(diary)
        await db.commit()
        await db.refresh(diary)

    return diary
