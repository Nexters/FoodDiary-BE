import uuid

from sqlalchemy import select
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
    Device 정보를 upsert 처리

    device_id로 기존 레코드를 조회하여:
    - 존재하면: user_id, token 등 업데이트 (기기 소유자 변경 대응)
    - 없으면: 새 레코드 생성

    Args:
        session: Async database session
        user_id: 사용자 UUID
        device_id: 디바이스 고유 ID
        device_token: 푸시 알림 토큰
        app_version: 앱 버전
        os_version: OS 버전
        is_active: 활성 여부

    Returns:
        생성 또는 업데이트된 Device
    """
    device = await _find_device_by_device_id(session, device_id)

    if device:
        return await _update_device(
            session, device, user_id, device_token, app_version, os_version, is_active
        )

    return await _create_device(
        session, user_id, device_id, device_token, app_version, os_version, is_active
    )


async def _find_device_by_device_id(
    session: AsyncSession,
    device_id: str,
) -> Device | None:
    result = await session.execute(
        select(Device).where(
            Device.device_id == device_id,
            Device.deleted_at.is_(None),
        )
    )
    return result.scalars().first()


async def _update_device(
    session: AsyncSession,
    device: Device,
    user_id: uuid.UUID,
    device_token: str | None,
    app_version: str,
    os_version: str,
    is_active: bool,
) -> Device:
    device.user_id = user_id
    device.device_token = device_token
    device.app_version = app_version
    device.os_version = os_version
    device.is_active = is_active
    await session.commit()
    await session.refresh(device)
    return device


async def _create_device(
    session: AsyncSession,
    user_id: uuid.UUID,
    device_id: str,
    device_token: str | None,
    app_version: str,
    os_version: str,
    is_active: bool,
) -> Device:
    device = Device(
        device_id=device_id,
        user_id=user_id,
        device_token=device_token,
        app_version=app_version,
        os_version=os_version,
        is_active=is_active,
    )
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return device
