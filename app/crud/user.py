from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    result = await session.execute(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    return result.scalars().first()


async def get_user_by_provider_id(
    session: AsyncSession,
    provider: str,
    provider_user_id: str,
) -> User | None:
    result = await session.execute(
        select(User).where(
            User.provider == provider,
            User.provider_user_id == provider_user_id,
            User.deleted_at.is_(None),
        )
    )
    return result.scalars().first()


async def save(session: AsyncSession, user: User) -> User:
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user
