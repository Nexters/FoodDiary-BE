from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import device as crud_device
from app.crud import user as crud_user
from app.models.device import Device
from app.models.user import User
from app.schemas.auth import OAuthProvider
from app.services import oauth2
from app.services.jwt import create_access_token
from app.services.user import generate_random_name


async def login(
    session: AsyncSession,
    provider: str,
    id_token: str,
    device_id: str,
    device_token: str | None,
    app_version: str,
    os_version: str,
    is_active: bool,
) -> tuple[User, bool, str]:
    provider_user_id, email = await oauth2.verify_oauth_token(
        OAuthProvider(provider), id_token
    )

    is_first = False
    user = await crud_user.get_user_by_provider_id(session, provider, provider_user_id)
    if user is None:
        user = User(
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            name=generate_random_name(),
        )
        is_first = True

    user.update_last_login()
    user = await crud_user.save(session, user)

    await crud_device.upsert_device(
        session,
        Device(
            user_id=user.id,
            device_id=device_id,
            device_token=device_token,
            app_version=app_version,
            os_version=os_version,
            is_active=is_active,
        ),
    )

    access_token = create_access_token(user_id=str(user.id), provider=provider)

    return user, is_first, access_token


async def login_dev(
    session: AsyncSession,
    email: str,
    device_id: str,
    device_token: str | None,
    app_version: str,
    os_version: str,
    is_active: bool,
) -> tuple[User, bool, str]:
    provider = "dev"
    provider_user_id = f"dev_{email}"

    is_first = False
    user = await crud_user.get_user_by_provider_id(session, provider, provider_user_id)
    if user is None:
        user = User(
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            name=generate_random_name(),
        )
        is_first = True

    user.update_last_login()
    user = await crud_user.save(session, user)

    await crud_device.upsert_device(
        session,
        Device(
            user_id=user.id,
            device_id=device_id,
            device_token=device_token,
            app_version=app_version,
            os_version=os_version,
            is_active=is_active,
        ),
    )

    access_token = create_access_token(user_id=str(user.id), provider=provider)

    return user, is_first, access_token


async def verify_user(session: AsyncSession, user_id: UUID) -> User | None:
    return await crud_user.get_user_by_id(session, user_id)
