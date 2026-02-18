"""batch_upload_photos_sync 서비스 통합 테스트"""

from datetime import date, datetime

import pytest
from sqlalchemy import select

from app.models import Diary, Photo
from app.models.user import User
from app.services.photo_service import batch_upload_photos_sync
from tests.fixtures.auth_fixtures import create_test_user_data
from tests.fixtures.photo_fixtures import create_test_upload_file, mock_exif_data

# ========================================
# Helper
# ========================================


async def _to_file_buffers(
    files: list,
) -> list[tuple[str, bytes, str]]:
    """UploadFile 목록을 (filename, bytes, content_type) 튜플 목록으로 변환"""
    result = []
    for f in files:
        content = await f.read()
        result.append(
            (f.filename or "test.jpg", content, f.content_type or "image/jpeg")
        )
    return result


@pytest.fixture
def patch_photo_externals(monkeypatch):
    """외부 의존성 mock (EXIF, 파일저장)"""

    def _patch(
        taken_at: datetime | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ):
        exif = mock_exif_data(taken_at=taken_at, latitude=latitude, longitude=longitude)
        monkeypatch.setattr(
            "app.services.photo_service.extract_exif_data",
            lambda f: exif,
        )
        monkeypatch.setattr(
            "app.services.photo_service.save_user_photo",
            _mock_save_user_photo,
        )

    return _patch


async def _mock_save_user_photo(user_id, file):
    return f"storage/photos/{user_id}/test.jpg"


# ========================================
# 테스트 케이스
# ========================================


@pytest.mark.asyncio
async def test_single_photo_upload(test_db_session, patch_photo_externals):
    """
    사진 1장 업로드 성공:
    - Diary 생성, Photo 생성
    """
    # Given
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()

    patch_photo_externals(taken_at=datetime(2026, 1, 15, 12, 0, 0))  # lunch
    file_buffers = await _to_file_buffers([create_test_upload_file()])

    # When
    results = await batch_upload_photos_sync(
        test_db_session, user.id, date(2026, 1, 15), file_buffers
    )

    # Then
    assert len(results) == 1
    assert results[0].time_type == "lunch"

    diary = await test_db_session.get(Diary, results[0].diary_id)
    assert diary is not None
    assert diary.photo_count == 1

    photos = (
        (
            await test_db_session.execute(
                select(Photo).where(Photo.diary_id == results[0].diary_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(photos) == 1


@pytest.mark.asyncio
async def test_two_photos_same_meal(test_db_session, patch_photo_externals):
    """
    같은 끼니 사진 2장:
    - 같은 Diary에 photo_count=2
    - Photo 2개 생성
    """
    # Given
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()

    patch_photo_externals(taken_at=datetime(2026, 1, 15, 12, 0, 0))  # lunch
    file_buffers = await _to_file_buffers(
        [create_test_upload_file("a.jpg"), create_test_upload_file("b.jpg")]
    )

    # When
    results = await batch_upload_photos_sync(
        test_db_session, user.id, date(2026, 1, 15), file_buffers
    )

    # Then
    assert len(results) == 2
    diary_id = results[0].diary_id

    diary = await test_db_session.get(Diary, diary_id)
    assert diary.photo_count == 2

    photos = (
        (await test_db_session.execute(select(Photo).where(Photo.diary_id == diary_id)))
        .scalars()
        .all()
    )
    assert len(photos) == 2


@pytest.mark.asyncio
async def test_two_photos_different_meals(test_db_session, monkeypatch):
    """
    다른 끼니 사진 2장:
    - Diary 2개 생성
    - 각각 photo_count=1
    """
    # Given
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()

    call_count = 0

    def mock_exif(f):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_exif_data(taken_at=datetime(2026, 1, 15, 8, 0, 0))  # breakfast
        return mock_exif_data(taken_at=datetime(2026, 1, 15, 19, 0, 0))  # dinner

    monkeypatch.setattr("app.services.photo_service.extract_exif_data", mock_exif)
    monkeypatch.setattr(
        "app.services.photo_service.save_user_photo", _mock_save_user_photo
    )

    file_buffers = await _to_file_buffers(
        [
            create_test_upload_file("morning.jpg"),
            create_test_upload_file("evening.jpg"),
        ]
    )

    # When
    results = await batch_upload_photos_sync(
        test_db_session, user.id, date(2026, 1, 15), file_buffers
    )

    # Then
    assert len(results) == 2
    time_types = {r.time_type for r in results}
    assert "breakfast" in time_types
    assert "dinner" in time_types

    for r in results:
        diary = await test_db_session.get(Diary, r.diary_id)
        assert diary.photo_count == 1


@pytest.mark.asyncio
async def test_upload_to_existing_diary(test_db_session, patch_photo_externals):
    """
    기존 Diary에 추가 업로드:
    - photo_count 증가
    """
    # Given
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()

    patch_photo_externals(taken_at=datetime(2026, 1, 15, 12, 0, 0))

    # 첫 번째 업로드
    file_buffers_1 = await _to_file_buffers([create_test_upload_file("1.jpg")])
    await batch_upload_photos_sync(
        test_db_session, user.id, date(2026, 1, 15), file_buffers_1
    )

    # When: 두 번째 업로드
    file_buffers_2 = await _to_file_buffers([create_test_upload_file("2.jpg")])
    results = await batch_upload_photos_sync(
        test_db_session, user.id, date(2026, 1, 15), file_buffers_2
    )

    # Then
    assert len(results) == 1
    diary = await test_db_session.get(Diary, results[0].diary_id)
    assert diary.photo_count == 2
