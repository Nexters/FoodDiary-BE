from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Diary, Photo


async def get_photos_by_diary_id(
    session: AsyncSession,
    diary_id: int,
) -> list[Photo]:
    rows = await session.execute(select(Photo).where(Photo.diary_id == diary_id))
    return list(rows.scalars().all())


async def create_photos(
    session: AsyncSession,
    photos: list[Photo],
) -> list[Photo]:
    session.add_all(photos)
    await session.flush()
    return photos


async def create_photo_for_diary(
    session: AsyncSession,
    diary: Diary,
    image_url: str,
    taken_at: datetime | None,
    taken_location: str | None,
) -> Photo:
    photo = Photo(
        diary_id=diary.id,
        image_url=image_url,
        taken_at=taken_at,
        taken_location=taken_location,
    )
    session.add(photo)
    diary.photo_count = (diary.photo_count or 0) + 1
    await session.flush()
    if diary.cover_photo_id is None:
        diary.cover_photo_id = photo.id
    return photo
