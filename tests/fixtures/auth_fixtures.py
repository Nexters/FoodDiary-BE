from datetime import UTC, datetime
from uuid import uuid4


def create_test_user_data(
    provider: str = "apple",
    provider_user_id: str = "apple_user_123",
    email: str = "test@apple.com",
):
    """테스트용 User 데이터 팩토리"""
    return {
        "id": uuid4(),
        "provider": provider,
        "provider_user_id": provider_user_id,
        "email": email,
        "last_login_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deleted_at": None,
    }


def create_login_request_payload(
    provider: str = "apple",
    id_token: str = "mock_valid_token",
    device_id: str = "test-device-001",
    device_token: str | None = "test-fcm-token",
    app_version: str = "1.0.0",
    os_version: str = "18.0",
    is_active: bool = False,
):
    """LoginRequest payload 팩토리"""
    return {
        "provider": provider,
        "id_token": id_token,
        "device_id": device_id,
        "device_token": device_token,
        "app_version": app_version,
        "os_version": os_version,
        "is_active": is_active,
    }
