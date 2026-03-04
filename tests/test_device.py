from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.crud.device import upsert_device
from app.models.device import Device
from app.models.user import User
from app.services.jwt import create_access_token
from tests.fixtures.auth_fixtures import (
    create_login_request_payload,
    create_test_user_data,
)

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


# ======================
# upsert_device_native 서비스 테스트 (PostgreSQL native upsert)
# ======================


@pytest.mark.asyncio
async def test_upsert_device_native_creates_new_device(test_db_session, test_user):
    """
    신규 Device 생성:
    - device_id가 DB에 없을 때 새 레코드 삽입
    - 반환된 Device의 모든 필드 검증
    """
    # When
    device = await upsert_device(
        test_db_session,
        Device(
            user_id=test_user.id,
            device_id="native-device-001",
            device_token="fcm-token-001",
            app_version="1.0.0",
            os_version="18.0",
            is_active=True,
        ),
    )

    # Then
    assert device.id is not None
    assert device.device_id == "native-device-001"
    assert device.user_id == test_user.id
    assert device.device_token == "fcm-token-001"
    assert device.app_version == "1.0.0"
    assert device.os_version == "18.0"
    assert device.is_active is True
    assert device.deleted_at is None


@pytest.mark.asyncio
async def test_upsert_device_native_updates_existing_device(test_db_session, test_user):
    """
    기존 Device 업데이트:
    - 동일 device_id로 재호출 시 같은 레코드 ID 유지
    - token, version 등 업데이트 확인
    - DB에 레코드가 1개만 존재
    """
    # Given
    first = await upsert_device(
        test_db_session,
        Device(
            user_id=test_user.id,
            device_id="native-device-002",
            device_token="old-token",
            app_version="1.0.0",
            os_version="17.0",
            is_active=True,
        ),
    )
    original_id = first.id

    # When
    updated = await upsert_device(
        test_db_session,
        Device(
            user_id=test_user.id,
            device_id="native-device-002",
            device_token="new-token",
            app_version="1.1.0",
            os_version="18.0",
            is_active=True,
        ),
    )

    # Then: 동일 레코드 업데이트, 새 레코드 미생성
    assert updated.id == original_id
    assert updated.device_token == "new-token"
    assert updated.app_version == "1.1.0"
    assert updated.os_version == "18.0"

    result = await test_db_session.execute(
        select(Device).where(Device.device_id == "native-device-002")
    )
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_upsert_device_native_changes_device_owner(test_db_session):
    """
    소유자 변경:
    - 동일 device_id에 다른 user_id로 upsert
    - user_id가 새 사용자로 업데이트, DB에 1개만 존재
    """
    # Given: 두 사용자 생성
    user1 = User(
        **create_test_user_data(email="native1@test.com", provider_user_id="native_1")
    )
    user2 = User(
        **create_test_user_data(email="native2@test.com", provider_user_id="native_2")
    )
    test_db_session.add_all([user1, user2])
    await test_db_session.commit()

    await upsert_device(
        test_db_session,
        Device(
            user_id=user1.id,
            device_id="shared-native-device",
            device_token="token-v1",
            app_version="1.0.0",
            os_version="18.0",
            is_active=True,
        ),
    )

    # When: user2로 동일 기기 upsert
    device = await upsert_device(
        test_db_session,
        Device(
            user_id=user2.id,
            device_id="shared-native-device",
            device_token="token-v2",
            app_version="1.0.0",
            os_version="18.0",
            is_active=True,
        ),
    )

    # Then: user_id가 user2로 변경, 레코드 1개만
    assert device.user_id == user2.id
    assert device.device_token == "token-v2"

    result = await test_db_session.execute(select(Device))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_upsert_device_native_inserts_when_soft_deleted(
    test_db_session, test_user
):
    """
    소프트 삭제 레코드가 있을 때 신규 삽입:
    - partial index (WHERE deleted_at IS NULL) 조건에 해당하지 않아 conflict 미발생
    - 삭제된 레코드와 별개로 새 레코드 생성
    """
    # Given: 소프트 삭제된 Device 존재
    deleted_device = Device(
        device_id="deleted-native-device",
        user_id=test_user.id,
        device_token="old-token",
        app_version="1.0.0",
        os_version="17.0",
        is_active=False,
        deleted_at=datetime.now(UTC),
    )
    test_db_session.add(deleted_device)
    await test_db_session.commit()

    # When: 동일 device_id로 upsert
    new_device = await upsert_device(
        test_db_session,
        Device(
            user_id=test_user.id,
            device_id="deleted-native-device",
            device_token="new-token",
            app_version="2.0.0",
            os_version="18.0",
            is_active=True,
        ),
    )

    # Then: 소프트 삭제 레코드와 별개로 새 레코드 생성 (총 2개)
    assert new_device.id != deleted_device.id
    assert new_device.deleted_at is None
    assert new_device.device_token == "new-token"

    result = await test_db_session.execute(
        select(Device).where(Device.device_id == "deleted-native-device")
    )
    assert len(result.scalars().all()) == 2


@pytest.mark.asyncio
async def test_upsert_device_native_handles_none_token(test_db_session, test_user):
    """
    device_token None 처리:
    - None으로 생성 후 값으로 업데이트 가능
    """
    # When: token 없이 생성
    device = await upsert_device(
        test_db_session,
        Device(
            user_id=test_user.id,
            device_id="no-token-native-device",
            device_token=None,
            app_version="1.0.0",
            os_version="18.0",
            is_active=False,
        ),
    )

    # Then
    assert device.device_token is None
    assert device.is_active is False

    # When: token 추가하여 업데이트
    updated = await upsert_device(
        test_db_session,
        Device(
            user_id=test_user.id,
            device_id="no-token-native-device",
            device_token="now-has-token",
            app_version="1.0.0",
            os_version="18.0",
            is_active=True,
        ),
    )

    # Then
    assert updated.device_token == "now-has-token"
    assert updated.is_active is True


@pytest.mark.asyncio
async def test_upsert_device_native_updated_at_refreshed(test_db_session, test_user):
    """
    conflict 발생 시 updated_at 갱신:
    - ON CONFLICT DO UPDATE SET updated_at = func.now() 동작 확인
    """
    # Given
    first = await upsert_device(
        test_db_session,
        Device(
            user_id=test_user.id,
            device_id="timestamp-native-device",
            device_token="token",
            app_version="1.0.0",
            os_version="18.0",
            is_active=True,
        ),
    )
    original_updated_at = first.updated_at

    # When: 재호출 (conflict → DO UPDATE)
    updated = await upsert_device(
        test_db_session,
        Device(
            user_id=test_user.id,
            device_id="timestamp-native-device",
            device_token="new-token",
            app_version="1.0.0",
            os_version="18.0",
            is_active=True,
        ),
    )

    # Then: updated_at이 갱신됨 (별개 트랜잭션이므로 >=)
    assert updated.updated_at >= original_updated_at
