from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as crud_user
from app.models.user import User
from app.utils.file_storage import delete_user_storage


class UserNotFoundError(Exception):
    pass


async def get_user(session: AsyncSession, user_id: UUID) -> User:
    user = await crud_user.get_user_by_id(session, user_id)
    if user is None:
        raise UserNotFoundError
    return user


async def delete_user(session: AsyncSession, user_id: UUID) -> None:
    user = await get_user(session, user_id)
    delete_user_storage(user_id)
    await crud_user.delete_user(session, user)
