from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device


async def upsert_device(session: AsyncSession, device: Device) -> Device:
    insert_stmt = pg_insert(Device).values(
        device_id=device.device_id,
        user_id=device.user_id,
        device_token=device.device_token,
        app_version=device.app_version,
        os_version=device.os_version,
        is_active=device.is_active,
    )
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=["device_id"],
        index_where=Device.deleted_at.is_(None),
        set_={
            "user_id": insert_stmt.excluded.user_id,
            "device_token": insert_stmt.excluded.device_token,
            "app_version": insert_stmt.excluded.app_version,
            "os_version": insert_stmt.excluded.os_version,
            "is_active": insert_stmt.excluded.is_active,
            "updated_at": func.now(),
        },
    ).returning(Device)
    result = await session.scalars(
        upsert_stmt,
        execution_options={"populate_existing": True},
    )
    await session.flush()
    return result.one()
