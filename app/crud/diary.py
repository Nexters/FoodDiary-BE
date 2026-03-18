from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Diary, Photo


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
