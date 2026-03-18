from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Photo


async def create_photos(
    session: AsyncSession,
    photos: list[Photo],
) -> list[Photo]:
    session.add_all(photos)
    await session.flush()
    return photos
