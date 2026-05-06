"""_batch_upload_photos_sync 유스케이스 통합 테스트 + _extract_top_restaurant 유닛 테스트"""  # noqa: E501

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.models import Diary, Photo
from app.models.user import User
from app.usecases.diary import _extract_top_restaurant
from app.usecases.photos import _batch_upload_photos_sync as batch_upload_photos_sync
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
            "app.usecases.photos.extract_exif_data",
            lambda f: exif,
        )
        monkeypatch.setattr(
            "app.usecases.photos.save_user_photo",
            _mock_save_user_photo,
        )

    return _patch


async def _mock_save_user_photo(user_id, file):
    return f"storage/photos/{user_id}/test.jpg"


# ========================================
# 업로드 통합 테스트
# ========================================


@pytest.mark.asyncio
async def test_single_photo_upload(test_db_session, patch_photo_externals):
    """
    사진 1장 업로드 성공:
    - Diary 생성, Photo 생성
    - cover_photo_id가 생성된 Photo.id와 일치
    """
    # Given
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()

    patch_photo_externals(
        taken_at=datetime(2026, 1, 15, 3, 0, 0, tzinfo=UTC)
    )  # KST 12:00 = lunch
    file_buffers = await _to_file_buffers([create_test_upload_file()])

    # When
    results = await batch_upload_photos_sync(
        test_db_session, user.id, date(2026, 1, 15), file_buffers
    )

    # Then
    assert len(results) == 1
    assert results[0].time_type == "lunch"
    assert results[0].is_new_diary is True

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
    assert diary.cover_photo_id == photos[0].id


@pytest.mark.asyncio
async def test_two_photos_same_meal(test_db_session, patch_photo_externals):
    """
    같은 끼니 사진 2장:
    - 같은 Diary에 photo_count=2
    - 첫 번째 Photo가 cover_photo_id, 두 번째는 변경 없음
    """
    # Given
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()

    patch_photo_externals(
        taken_at=datetime(2026, 1, 15, 3, 0, 0, tzinfo=UTC)
    )  # KST 12:00 = lunch
    file_buffers = await _to_file_buffers(
        [create_test_upload_file("a.jpg"), create_test_upload_file("b.jpg")]
    )

    # When
    results = await batch_upload_photos_sync(
        test_db_session, user.id, date(2026, 1, 15), file_buffers
    )

    # Then
    assert len(results) == 2
    assert results[0].diary_id == results[1].diary_id  # 같은 다이어리

    diary_id = results[0].diary_id
    diary = await test_db_session.get(Diary, diary_id)
    assert diary.photo_count == 2

    photos = (
        (
            await test_db_session.execute(
                select(Photo).where(Photo.diary_id == diary_id).order_by(Photo.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(photos) == 2
    assert diary.cover_photo_id == photos[0].id  # 첫 번째 사진이 커버
    assert diary.cover_photo_id != photos[1].id  # 두 번째 사진은 커버 아님


@pytest.mark.asyncio
async def test_two_photos_different_meals(test_db_session, monkeypatch):
    """
    다른 끼니 사진 2장:
    - Diary 2개 생성 (각각 다른 time_type)
    - 각각 photo_count=1, cover_photo_id 설정됨
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
            return mock_exif_data(
                taken_at=datetime(2026, 1, 14, 23, 0, 0, tzinfo=UTC)
            )  # KST 8:00 = breakfast
        return mock_exif_data(
            taken_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        )  # KST 19:00 = dinner

    monkeypatch.setattr("app.usecases.photos.extract_exif_data", mock_exif)
    monkeypatch.setattr("app.usecases.photos.save_user_photo", _mock_save_user_photo)

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

    diary_ids = {r.diary_id for r in results}
    assert len(diary_ids) == 2  # 서로 다른 다이어리

    for r in results:
        diary = await test_db_session.get(Diary, r.diary_id)
        assert diary.photo_count == 1
        assert diary.cover_photo_id is not None


@pytest.mark.asyncio
async def test_upload_to_existing_diary(test_db_session, patch_photo_externals):
    """
    기존 Diary에 추가 업로드:
    - photo_count 증가
    - diary_id 동일
    - is_new_diary=False
    """
    # Given
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.commit()

    patch_photo_externals(taken_at=datetime(2026, 1, 15, 3, 0, 0, tzinfo=UTC))

    # 첫 번째 업로드
    file_buffers_1 = await _to_file_buffers([create_test_upload_file("1.jpg")])
    results_1 = await batch_upload_photos_sync(
        test_db_session, user.id, date(2026, 1, 15), file_buffers_1
    )
    original_diary_id = results_1[0].diary_id

    # When: 두 번째 업로드
    file_buffers_2 = await _to_file_buffers([create_test_upload_file("2.jpg")])
    results_2 = await batch_upload_photos_sync(
        test_db_session, user.id, date(2026, 1, 15), file_buffers_2
    )

    # Then
    assert len(results_2) == 1
    assert results_2[0].diary_id == original_diary_id  # 같은 다이어리
    assert results_2[0].is_new_diary is False  # 기존 다이어리

    diary = await test_db_session.get(Diary, original_diary_id)
    assert diary.photo_count == 2


# ========================================
# _extract_top_restaurant 유닛 테스트
# ========================================


def test_extract_top_restaurant_valid_category():
    """유효한 category는 그대로 반환되며 모든 필드가 올바르게 매핑된다."""
    result = [
        {
            "restaurant_name": "테스트식당",
            "restaurant_url": "https://place.map.kakao.com/12345",
            "road_address": "서울시 강남구 테헤란로 1",
            "category": "korean",
            "memo": "맛있는 한식집",
            "tags": ["김치찌개"],
        }
    ]

    top = _extract_top_restaurant(result)

    assert top is not None
    assert top["restaurant_name"] == "테스트식당"
    assert top["restaurant_url"] == "https://place.map.kakao.com/12345"
    assert top["road_address"] == "서울시 강남구 테헤란로 1"
    assert top["category"] == "korean"
    assert top["note"] == "맛있는 한식집"


def test_extract_top_restaurant_invalid_category():
    """유효하지 않은 category는 None으로 변환된다."""
    result = [
        {
            "restaurant_name": "식당",
            "restaurant_url": None,
            "road_address": None,
            "category": "양식",  # 유효하지 않은 값
            "memo": None,
            "tags": [],
        }
    ]

    top = _extract_top_restaurant(result)

    assert top is not None
    assert top["category"] is None


def test_extract_top_restaurant_maps_memo_to_note():
    """LLM이 반환한 memo 필드가 note 키로 매핑된다."""
    result = [
        {
            "restaurant_name": "식당",
            "restaurant_url": None,
            "road_address": None,
            "category": "etc",
            "memo": "브리핑 내용입니다.",
            "tags": [],
        }
    ]

    top = _extract_top_restaurant(result)

    assert top is not None
    assert top["note"] == "브리핑 내용입니다."
    assert "memo" not in top


def test_extract_top_restaurant_empty_result():
    """빈 result 배열이면 None을 반환한다."""
    assert _extract_top_restaurant([]) is None


def test_extract_top_restaurant_uses_first_result_only():
    """result에 여러 항목이 있어도 첫 번째(result[0])만 사용한다."""
    result = [
        {
            "restaurant_name": "첫 번째 식당",
            "restaurant_url": None,
            "road_address": None,
            "category": "korean",
            "memo": None,
            "tags": [],
        },
        {
            "restaurant_name": "두 번째 식당",
            "restaurant_url": None,
            "road_address": None,
            "category": "japanese",
            "memo": None,
            "tags": [],
        },
    ]

    top = _extract_top_restaurant(result)

    assert top is not None
    assert top["restaurant_name"] == "첫 번째 식당"
    assert top["category"] == "korean"
