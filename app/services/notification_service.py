"""범용 알림 서비스"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.services.fcm_sender import send_notification, send_silent_push

logger = logging.getLogger(__name__)


async def send_silent_notification(
    db: AsyncSession,
    device_id: str | None,
    data: dict[str, str],
) -> bool:
    """device_id로 디바이스를 조회하고 silent push를 전송합니다.

    is_active 여부와 관계없이 전송합니다.
    device_id가 없으면 로그만 남기고 False를 반환합니다.

    Args:
        db: 데이터베이스 세션
        device_id: 디바이스 고유 ID
        data: 전송할 데이터 페이로드

    Returns:
        전송 성공 여부
    """
    if not device_id:
        logger.warning("device_id가 없어 silent push 전송 생략")
        return False

    device_token = await _get_device_token(db, device_id)
    if not device_token:
        return False

    return send_silent_push(token=device_token, data=data)


async def send_push_notification(
    db: AsyncSession,
    device_id: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> bool:
    """device_id로 디바이스를 조회하고 푸시 알림을 전송합니다.

    is_active=True인 디바이스에만 전송합니다.

    Args:
        db: 데이터베이스 세션
        device_id: 디바이스 고유 ID
        title: 알림 제목
        body: 알림 본문
        data: 추가 데이터 페이로드 (선택)

    Returns:
        전송 성공 여부
    """
    device = await _find_active_device(db, device_id)
    if not device or not device.device_token:
        return False

    return send_notification(
        token=device.device_token, title=title, body=body, data=data
    )


async def _get_device_token(db: AsyncSession, device_id: str) -> str | None:
    """device_id로 디바이스 토큰을 조회합니다 (is_active 무관)."""
    result = await db.execute(
        select(Device.device_token).where(
            Device.device_id == device_id,
            Device.deleted_at.is_(None),
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        logger.warning(f"디바이스 토큰 없음: device_id={device_id}")
    return token


async def _find_active_device(db: AsyncSession, device_id: str) -> Device | None:
    """is_active=True인 디바이스를 조회합니다."""
    result = await db.execute(
        select(Device).where(
            Device.device_id == device_id,
            Device.is_active.is_(True),
            Device.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()
