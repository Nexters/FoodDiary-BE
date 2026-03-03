import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device


async def upsert_device(
    session: AsyncSession,
    user_id: uuid.UUID,
    device_id: str,
    device_token: str | None,
    app_version: str,
    os_version: str,
    is_active: bool,
) -> Device:
    """
    PostgreSQL native upsert로 Device 처리

    idx_device_device_id (partial unique index: WHERE deleted_at IS NULL)를 기준으로
    INSERT ... ON CONFLICT DO UPDATE 실행.
    소프트 삭제된 레코드는 conflict 대상에서 제외됨.

    .returning(Device)로 session을 통해 ORM 객체를 직접 반환.
    populate_existing=True로 identity map의 stale 캐시를 RETURNING 값으로 갱신.
    """
    insert_stmt = pg_insert(Device).values(
        device_id=device_id,
        user_id=user_id,
        device_token=device_token,
        app_version=app_version,
        os_version=os_version,
        is_active=is_active,
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
    device = result.one()
    await session.commit()
    return device
