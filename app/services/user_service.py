from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.file_storage import delete_user_storage


async def get_user(session: AsyncSession, user_id: UUID) -> User:
    return await _get_active_user(session, user_id)


async def delete_user(session: AsyncSession, user_id: UUID) -> None:
    user = await _get_active_user(session, user_id)
    delete_user_storage(user_id)
    await _delete_user_from_db(session, user)


async def _get_active_user(session: AsyncSession, user_id: UUID) -> User:
    result = await session.execute(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다.",
        )
    return user


async def _delete_user_from_db(session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.commit()
