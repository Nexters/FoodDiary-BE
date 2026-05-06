"""photos 라우터 통합 테스트"""

import pytest

from app.models.user import User
from app.schemas.photo import BatchUploadResponse, DiaryUploadResult
from app.services.jwt import create_access_token
from tests.fixtures.auth_fixtures import create_test_user_data
from tests.fixtures.photo_fixtures import create_test_image_bytes

# ========================================
# Helper
# ========================================


@pytest.fixture
def mock_batch_upload_photos(monkeypatch):
    """batch_upload_photos usecase 전체를 mock — DB/LLM/FCM 없이 라우터 레이어만 검증"""

    async def _mock(**kwargs) -> BatchUploadResponse:
        return BatchUploadResponse(
            diary_date="2026-01-15",
            diaries=[
                DiaryUploadResult(
                    diary_id=20,
                    diary_status="processing",
                    time_type="lunch",
                )
            ],
        )

    monkeypatch.setattr("app.routers.photos.batch_upload_photos", _mock)


# ========================================
# 테스트 케이스
# ========================================


@pytest.mark.asyncio
async def test_batch_upload_success(
    test_client, test_db_session, mock_batch_upload_photos
):
    """
    POST /photos/batch-upload 성공:
    - 200 + BatchUploadResponse 반환
    - diary_date, diary_id, diary_status, time_type 검증
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
    assert data["diary_date"] == "2026-01-15"
    assert len(data["diaries"]) == 1
    assert data["diaries"][0]["diary_id"] == 20
    assert data["diaries"][0]["diary_status"] == "processing"
    assert data["diaries"][0]["time_type"] == "lunch"


@pytest.mark.asyncio
async def test_batch_upload_invalid_date(
    test_client, test_db_session, mock_batch_upload_photos
):
    """
    날짜 형식 오류 → 400 반환 (usecase 도달 전 라우터에서 차단)
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
    test_client, test_db_session, mock_batch_upload_photos
):
    """
    사진 미첨부 → FastAPI 필드 검증으로 422 반환
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
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_batch_upload_requires_auth(test_client):
    """
    Authorization 헤더 없음 → 403 반환
    """
    image_bytes = create_test_image_bytes()

    response = await test_client.post(
        "/photos/batch-upload",
        data={"date": "2026-01-15", "device_id": "test-device"},
        files=[("photos", ("test.jpg", image_bytes, "image/jpeg"))],
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_batch_upload_non_image_file_rejected(
    test_client, test_db_session, mock_batch_upload_photos
):
    """
    이미지가 아닌 파일 포함 → 400 반환 (라우터 validation)
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
        files=[("photos", ("doc.pdf", b"PDF content", "application/pdf"))],
        headers={"Authorization": f"Bearer {token}"},
    )

    # Then
    assert response.status_code == 400
