import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.device import Device
from app.models.user import User
from tests.fixtures.auth_fixtures import (
    create_login_request_payload,
    create_test_user_data,
)

# ======================
# Device Service 테스트 (upsert 로직)
# ======================


@pytest.mark.asyncio
async def test_upsert_device_creates_new_device(test_db_session):
    """
    신규 Device 생성 테스트:
    - device_id가 DB에 없을 때
    - 새 Device 레코드 생성
    """
    from app.services.device import upsert_device

    # Given: 사용자 생성
    user_data = create_test_user_data()
    user = User(**user_data)
    test_db_session.add(user)
    await test_db_session.commit()

    # When: upsert_device 호출
    device = await upsert_device(
        test_db_session,
        user_id=user.id,
        device_id="device-abc-123",
        device_token="fcm-token-xyz",
        app_version="1.0.0",
        os_version="18.2",
        is_active=True,
    )

    # Then: Device 생성 확인
    assert device.id is not None
    assert device.device_id == "device-abc-123"
    assert device.user_id == user.id
    assert device.device_token == "fcm-token-xyz"
    assert device.app_version == "1.0.0"
    assert device.os_version == "18.2"
    assert device.is_active is True


@pytest.mark.asyncio
async def test_upsert_device_updates_existing_device(test_db_session):
    """
    기존 Device 업데이트 테스트:
    - 동일한 device_id로 다시 호출
    - user_id, token 등 업데이트
    - 새 레코드 생성되지 않음
    """
    from app.services.device import upsert_device

    # Given: 사용자와 Device 생성
    user_data = create_test_user_data()
    user = User(**user_data)
    test_db_session.add(user)
    await test_db_session.commit()

    device = await upsert_device(
        test_db_session,
        user_id=user.id,
        device_id="device-abc-123",
        device_token="old-token",
        app_version="1.0.0",
        os_version="17.0",
        is_active=True,
    )
    original_id = device.id

    # When: 동일 device_id로 다시 upsert (토큰, 버전 변경)
    updated_device = await upsert_device(
        test_db_session,
        user_id=user.id,
        device_id="device-abc-123",
        device_token="new-token",
        app_version="1.1.0",
        os_version="18.0",
        is_active=True,
    )

    # Then: 기존 레코드 업데이트, 새 레코드 생성되지 않음
    assert updated_device.id == original_id
    assert updated_device.device_token == "new-token"
    assert updated_device.app_version == "1.1.0"
    assert updated_device.os_version == "18.0"

    result = await test_db_session.execute(select(Device))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_upsert_device_changes_user(test_db_session):
    """
    Device 소유자 변경 테스트:
    - 동일 device_id에 다른 user_id로 upsert
    - user_id가 새 사용자로 업데이트
    """
    from app.services.device import upsert_device

    # Given: 두 사용자 생성
    user1_data = create_test_user_data(
        email="user1@test.com",
        provider_user_id="user_1",
    )
    user2_data = create_test_user_data(
        email="user2@test.com",
        provider_user_id="user_2",
    )
    user1 = User(**user1_data)
    user2 = User(**user2_data)
    test_db_session.add_all([user1, user2])
    await test_db_session.commit()

    # user1으로 Device 등록
    await upsert_device(
        test_db_session,
        user_id=user1.id,
        device_id="shared-device",
        device_token="token-v1",
        app_version="1.0.0",
        os_version="18.0",
        is_active=True,
    )

    # When: 같은 기기에서 user2로 로그인 (소유자 변경)
    device = await upsert_device(
        test_db_session,
        user_id=user2.id,
        device_id="shared-device",
        device_token="token-v2",
        app_version="1.0.0",
        os_version="18.0",
        is_active=True,
    )

    # Then: user_id가 user2로 변경
    assert device.user_id == user2.id
    assert device.device_token == "token-v2"

    result = await test_db_session.execute(select(Device))
    assert len(result.scalars().all()) == 1


# ======================
# Device Router 테스트 (POST /members/me/device)
# ======================


@pytest.mark.asyncio
async def test_register_device_creates_new(
    test_client,
    test_db_session,
):
    """
    POST /members/me/device 신규 등록 테스트:
    - 인증된 사용자가 Device 등록
    - 200 응답 및 Device 정보 반환
    """
    # Given: 사용자 생성 및 JWT 발급
    user_data = create_test_user_data(email="device-test@example.com")
    user = User(**user_data)
    test_db_session.add(user)
    await test_db_session.commit()

    token = create_access_token(user_id=str(user.id), provider="apple")

    # When: Device 등록
    response = await test_client.post(
        "/members/me/device",
        json={
            "device_id": "new-device-001",
            "device_token": "fcm-new-token",
            "app_version": "2.0.0",
            "os_version": "18.2",
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Then: 성공 응답
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "new-device-001"
    assert data["device_token"] == "fcm-new-token"
    assert data["app_version"] == "2.0.0"
    assert data["os_version"] == "18.2"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_device_upsert_existing(
    test_client,
    test_db_session,
):
    """
    POST /members/me/device upsert 테스트:
    - 동일한 device_id로 두 번 호출
    - 두 번째 호출에서 토큰 업데이트
    - Device 레코드는 1개만 존재
    """
    # Given: 사용자 생성 및 JWT 발급
    user_data = create_test_user_data(email="upsert-test@example.com")
    user = User(**user_data)
    test_db_session.add(user)
    await test_db_session.commit()

    token = create_access_token(user_id=str(user.id), provider="apple")
    headers = {"Authorization": f"Bearer {token}"}

    # 첫 번째 등록
    await test_client.post(
        "/members/me/device",
        json={
            "device_id": "upsert-device",
            "device_token": "old-token",
            "app_version": "1.0.0",
            "os_version": "17.0",
            "is_active": True,
        },
        headers=headers,
    )

    # When: 동일 device_id로 재등록
    response = await test_client.post(
        "/members/me/device",
        json={
            "device_id": "upsert-device",
            "device_token": "updated-token",
            "app_version": "1.1.0",
            "os_version": "18.0",
            "is_active": True,
        },
        headers=headers,
    )

    # Then: 업데이트된 정보 반환
    assert response.status_code == 200
    data = response.json()
    assert data["device_token"] == "updated-token"
    assert data["app_version"] == "1.1.0"

    # DB에 1개만 존재 확인
    result = await test_db_session.execute(
        select(Device).where(Device.device_id == "upsert-device")
    )
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_register_device_requires_auth(test_client):
    """
    POST /members/me/device 인증 필수 테스트:
    - 토큰 없이 호출
    - 403 Forbidden 응답 (HTTPBearer 기본 동작)
    """
    response = await test_client.post(
        "/members/me/device",
        json={
            "device_id": "no-auth-device",
            "device_token": "token",
            "app_version": "1.0.0",
            "os_version": "18.0",
            "is_active": False,
        },
    )
    assert response.status_code == 403


# ======================
# 로그인 시 Device 자동 등록 테스트
# ======================


@pytest.mark.asyncio
async def test_login_creates_device(
    test_client,
    test_db_session,
    mock_verify_apple_token_success,
):
    """
    로그인 시 Device 자동 등록 테스트:
    - OAuth 로그인 성공 시 Device 레코드 생성
    """
    # When: device 정보 포함하여 로그인 (알림 권한 허용)
    payload = create_login_request_payload(
        device_id="login-device-001",
        device_token="login-fcm-token",
        app_version="1.0.0",
        os_version="18.0",
        is_active=True,
    )
    response = await test_client.post("/auth/login", json=payload)

    # Then: 로그인 성공
    assert response.status_code == 200

    # Device가 DB에 생성되었는지 확인
    result = await test_db_session.execute(
        select(Device).where(Device.device_id == "login-device-001")
    )
    device = result.scalars().first()
    assert device is not None
    assert device.device_token == "login-fcm-token"
    assert device.app_version == "1.0.0"
    assert device.os_version == "18.0"
    assert device.is_active is True


@pytest.mark.asyncio
async def test_dev_login_creates_device(
    test_client,
    test_db_session,
    monkeypatch,
):
    """
    Dev 로그인 시 Device 자동 등록 테스트:
    - dev/login 호출 시 Device 레코드 생성
    """
    # Given: DEBUG=True 설정
    monkeypatch.setattr("app.routers.auth.settings.DEBUG", True)

    # When: dev 로그인 (device 정보 포함, 알림 권한 미허용)
    response = await test_client.post(
        "/auth/dev/login",
        json={
            "email": "devlogin@example.com",
            "device_id": "dev-login-device",
            "device_token": "dev-fcm-token",
            "app_version": "0.1.0",
            "os_version": "17.5",
            "is_active": False,
        },
    )

    # Then: 로그인 성공
    assert response.status_code == 200

    # Device가 DB에 생성되었는지 확인
    result = await test_db_session.execute(
        select(Device).where(Device.device_id == "dev-login-device")
    )
    device = result.scalars().first()
    assert device is not None
    assert device.device_token == "dev-fcm-token"
    assert device.app_version == "0.1.0"
    assert device.os_version == "17.5"
    assert device.is_active is False
