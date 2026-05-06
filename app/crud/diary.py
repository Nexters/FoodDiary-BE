import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Diary, DiaryAnalysis, Photo
from app.utils.timezone import kst_date_to_utc

logger = logging.getLogger(__name__)


async def get_or_create_diary(
    session: AsyncSession,
    user_id: UUID,
    diary_date: date,
    time_type: str,
) -> tuple[Diary, bool]:
    diary_datetime = kst_date_to_utc(diary_date)
    stmt = select(Diary).where(
        Diary.user_id == user_id,
        Diary.diary_date == diary_datetime,
        Diary.time_type == time_type,
        Diary.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    diary = result.scalar_one_or_none()
    if diary is None:
        diary = Diary(
            user_id=user_id,
            diary_date=diary_datetime,
            time_type=time_type,
            photo_count=0,
        )
        session.add(diary)
        await session.flush()
        return diary, True
    return diary, False


async def save_diary_analysis(
    session: AsyncSession,
    diary_id: int,
    result: list,
) -> None:
    existing = await session.get(DiaryAnalysis, diary_id)
    if existing:
        existing.result = result
    else:
        session.add(DiaryAnalysis(diary_id=diary_id, result=result))
    diary = await session.get(Diary, diary_id)
    if diary and result:
        diary.tags = result[0].get("tags", [])


async def get_stale_processing_diaries(
    session: AsyncSession,
    stale_before: datetime,
) -> list[Diary]:
    stmt = (
        select(Diary)
        .where(
            Diary.analysis_status == "processing",
            Diary.updated_at < stale_before,
            Diary.deleted_at.is_(None),
        )
        .order_by(Diary.updated_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_pending_diaries(session: AsyncSession) -> list[Diary]:
    stmt = select(Diary).where(
        Diary.analysis_status == "pending",
        Diary.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


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


async def mark_diaries_done(session: AsyncSession, diary_ids: list[int]) -> None:
    await session.execute(
        update(Diary)
        .where(Diary.id.in_(diary_ids), Diary.analysis_status == "processing")
        .values(analysis_status="done")
    )


async def mark_diaries_failed(session: AsyncSession, diary_ids: list[int]) -> None:
    await session.execute(
        update(Diary).where(Diary.id.in_(diary_ids)).values(analysis_status="failed")
    )


async def mark_diaries_pending(session: AsyncSession, diary_ids: list[int]) -> None:
    await session.execute(
        update(Diary).where(Diary.id.in_(diary_ids)).values(analysis_status="pending")
    )


async def expire_stale_processing_diaries(
    session: AsyncSession,
    stale_before: datetime,
) -> int:
    result = await session.execute(
        update(Diary)
        .where(
            Diary.analysis_status == "processing",
            Diary.updated_at < stale_before,
            Diary.deleted_at.is_(None),
        )
        .values(analysis_status="pending")
        .returning(Diary.id)
    )
    return len(result.scalars().all())


async def claim_diary_for_processing(session: AsyncSession, diary_id: int) -> bool:
    """pending → processing 원자적 전환 + send_cnt 증가.

    다른 프로세스가 이미 클레임한 경우 False 반환.
    """
    result = await session.execute(
        update(Diary)
        .where(Diary.id == diary_id, Diary.analysis_status == "pending")
        .values(analysis_status="processing", send_cnt=Diary.send_cnt + 1)
        .returning(Diary.id)
    )
    await session.commit()
    return result.scalar_one_or_none() is not None


async def apply_top_restaurant(
    session: AsyncSession,
    diary_id: int,
    restaurant_name: str | None,
    restaurant_url: str | None,
    road_address: str | None,
    category: str | None,
    note: str | None,
) -> None:
    diary = await session.get(Diary, diary_id)
    if not diary:
        return

    diary.restaurant_name = restaurant_name
    diary.restaurant_url = restaurant_url
    diary.road_address = road_address
    diary.category = category
    if note:
        diary.note = note

    row = await session.execute(
        select(Photo.id).where(Photo.diary_id == diary_id).order_by(Photo.id).limit(1)
    )
    first_photo_id = row.scalar_one_or_none()
    if first_photo_id:
        diary.cover_photo_id = first_photo_id
