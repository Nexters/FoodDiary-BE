"""photos 라우터 통합 테스트"""

import pytest

from app.core.security import create_access_token
from app.models.user import User
from tests.fixtures.auth_fixtures import create_test_user_data
from tests.fixtures.photo_fixtures import create_test_image_bytes

# ========================================
# Helper
# ========================================


@pytest.fixture
def mock_photo_services(monkeypatch):
    """photo_service 함수들 mock"""
    from app.services.photo_service import PhotoSyncResult

    async def _mock_batch_upload_photos_sync(db, user_id, target_date, file_buffers):
        return [
            PhotoSyncResult(
                photo_id=100,
                diary_id=20,
                time_type="lunch",
                image_url="storage/photos/test/test.jpg",
            )
        ]

    async def _mock_analyze_and_notify(**kwargs):
        pass

    monkeypatch.setattr(
        "app.routers.photos.batch_upload_photos_sync",
        _mock_batch_upload_photos_sync,
    )
    monkeypatch.setattr(
        "app.routers.photos.analyze_and_notify",
        _mock_analyze_and_notify,
    )


# ========================================
# 테스트 케이스
# ========================================


@pytest.mark.asyncio
async def test_batch_upload_success(test_client, test_db_session, mock_photo_services):
    """
    POST /photos/batch-upload 성공:
    - 200 + message 반환
    """
    # Given
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()

    token = create_access_token(user_id=str(user.id), provider="apple")
    image_bytes = create_test_image_bytes()

    # When
    response = await test_client.post(
        "/photos/batch-upload",
        data={"date": "2026-01-15", "device_id": "test-device"},
        files=[("photos", ("test.jpg", image_bytes, "image/jpeg"))],
        headers={"Authorization": f"Bearer {token}"},
    )

    # Then
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["photo_id"] == 100
    assert data["results"][0]["diary_id"] == 20
    assert data["results"][0]["analysis_status"] == "processing"


@pytest.mark.asyncio
async def test_batch_upload_invalid_date(
    test_client, test_db_session, mock_photo_services
):
    """
    날짜 형식 오류:
    - 400 반환
    """
    # Given
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()

    token = create_access_token(user_id=str(user.id), provider="apple")
    image_bytes = create_test_image_bytes()

    # When
    response = await test_client.post(
        "/photos/batch-upload",
        data={"date": "invalid-date", "device_id": "test-device"},
        files=[("photos", ("test.jpg", image_bytes, "image/jpeg"))],
        headers={"Authorization": f"Bearer {token}"},
    )

    # Then
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_batch_upload_no_photos(
    test_client, test_db_session, mock_photo_services
):
    """
    사진 미첨부:
    - 400 반환
    """
    # Given
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()

    token = create_access_token(user_id=str(user.id), provider="apple")

    # When
    response = await test_client.post(
        "/photos/batch-upload",
        data={"date": "2026-01-15", "device_id": "test-device"},
        files=[],
        headers={"Authorization": f"Bearer {token}"},
    )

    # Then
    assert response.status_code == 422  # FastAPI validates required field


@pytest.mark.asyncio
async def test_batch_upload_requires_auth(test_client):
    """
    인증 없음:
    - 403 반환
    """
    image_bytes = create_test_image_bytes()

    # When
    response = await test_client.post(
        "/photos/batch-upload",
        data={"date": "2026-01-15", "device_id": "test-device"},
        files=[("photos", ("test.jpg", image_bytes, "image/jpeg"))],
    )

    # Then
    assert response.status_code == 403
