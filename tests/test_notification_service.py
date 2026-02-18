"""notification_service 통합 테스트"""

import pytest

from app.models.device import Device
from app.models.user import User
from app.services.notification_service import (
    send_push_notification,
    send_silent_notification,
)
from tests.fixtures.auth_fixtures import create_test_user_data

# ========================================
# Helper
# ========================================


@pytest.fixture
def mock_fcm(monkeypatch):
    """FCM 전송 mock"""
    monkeypatch.setattr(
        "app.services.notification_service.send_silent_push",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        "app.services.notification_service.send_notification",
        lambda **kwargs: True,
    )


async def _create_user_with_device(
    db, device_id: str = "test-device", is_active: bool = True
):
    """사용자 + 디바이스 생성"""
    user = User(**create_test_user_data())
    db.add(user)
    await db.commit()

    device = Device(
        user_id=user.id,
        device_id=device_id,
        device_token="fcm-token-abc",
        app_version="1.0.0",
        os_version="18.0",
        is_active=is_active,
    )
    db.add(device)
    await db.commit()

    return user, device


# ========================================
# send_silent_notification 테스트
# ========================================


@pytest.mark.asyncio
async def test_send_silent_notification_success(test_db_session, mock_fcm):
    """
    send_silent_notification 성공:
    - device_token 조회 + silent push 전송
    """
    # Given
    _, device = await _create_user_with_device(test_db_session)

    # When
    result = await send_silent_notification(
        db=test_db_session,
        device_id=device.device_id,
        data={"type": "test"},
    )

    # Then
    assert result is True


@pytest.mark.asyncio
async def test_send_silent_notification_device_not_found(test_db_session, mock_fcm):
    """
    send_silent_notification 디바이스 없음:
    - False 반환
    """
    # When
    result = await send_silent_notification(
        db=test_db_session,
        device_id="non-existent-device",
        data={"type": "test"},
    )

    # Then
    assert result is False


# ========================================
# send_push_notification 테스트
# ========================================


@pytest.mark.asyncio
async def test_send_push_notification_success(test_db_session, mock_fcm):
    """
    send_push_notification 성공:
    - is_active=True 디바이스에 전송
    """
    # Given
    _, device = await _create_user_with_device(test_db_session, is_active=True)

    # When
    result = await send_push_notification(
        db=test_db_session,
        device_id=device.device_id,
        title="테스트",
        body="테스트 알림",
    )

    # Then
    assert result is True


@pytest.mark.asyncio
async def test_send_push_notification_inactive_device(test_db_session, mock_fcm):
    """
    send_push_notification is_active=False:
    - False 반환
    """
    # Given
    _, device = await _create_user_with_device(test_db_session, is_active=False)

    # When
    result = await send_push_notification(
        db=test_db_session,
        device_id=device.device_id,
        title="테스트",
        body="테스트 알림",
    )

    # Then
    assert result is False
