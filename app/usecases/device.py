from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import device as crud_device
from app.models.device import Device


async def register_device(
    session: AsyncSession,
    user_id: UUID,
    device_id: str,
    device_token: str | None,
    app_version: str,
    os_version: str,
    is_active: bool,
) -> Device:
    return await crud_device.upsert_device(
        session,
        Device(
            user_id=user_id,
            device_id=device_id,
            device_token=device_token,
            app_version=app_version,
            os_version=os_version,
            is_active=is_active,
        ),
    )
