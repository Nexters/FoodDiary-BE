from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Diary, Photo
from app.utils.timezone import kst_date_to_utc


async def get_diary(
    session: AsyncSession,
    diary_id: int,
) -> Diary | None:
    stmt = (
        select(Diary)
        .where(
            Diary.id == diary_id,
            Diary.deleted_at.is_(None),
        )
        .options(
            selectinload(Diary.photos),
            selectinload(Diary.cover_photo),
            selectinload(Diary.analysis),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_diary_for_update(
    session: AsyncSession,
    diary_id: int,
) -> Diary | None:
    stmt = (
        select(Diary)
        .where(
            Diary.id == diary_id,
            Diary.deleted_at.is_(None),
        )
        .with_for_update()
        .options(
            selectinload(Diary.photos),
            selectinload(Diary.cover_photo),
            selectinload(Diary.analysis),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_diaries_by_date_range(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
) -> list[Diary]:
    start_bound = kst_date_to_utc(start_date)
    end_bound = kst_date_to_utc(end_date + timedelta(days=1))
    stmt = (
        select(Diary)
        .where(
            Diary.user_id == user_id,
            Diary.diary_date >= start_bound,
            Diary.diary_date < end_bound,
            Diary.deleted_at.is_(None),
        )
        .options(
            selectinload(Diary.photos),
            selectinload(Diary.cover_photo),
            selectinload(Diary.analysis),
        )
        .order_by(Diary.diary_date, Diary.time_type)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_diaries_for_insights(
    session: AsyncSession,
    user_id: UUID,
    start: datetime,
    end: datetime,
    *,
    load_cover_photo: bool = False,
) -> list[Diary]:
    """기간 내 다이어리 경량 조회 (start inclusive, end exclusive, UTC datetime)"""
    stmt = select(Diary).where(
        Diary.user_id == user_id,
        Diary.diary_date >= start,
        Diary.diary_date < end,
        Diary.deleted_at.is_(None),
    )
    if load_cover_photo:
        stmt = stmt.options(selectinload(Diary.cover_photo))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_photos(
    session: AsyncSession,
    photo_ids: set[int],
) -> None:
    if not photo_ids:
        return
    await session.execute(delete(Photo).where(Photo.id.in_(photo_ids)))


async def delete_diary(session: AsyncSession, diary: Diary) -> None:
    diary.deleted_at = datetime.now(UTC)
    await session.flush()
