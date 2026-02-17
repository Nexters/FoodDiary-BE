"""다이어리 테스트용 fixture 함수들"""

from datetime import UTC, datetime
from uuid import UUID


def create_diary_data(
    user_id: UUID,
    diary_date: datetime | None = None,
    time_type: str = "lunch",
    restaurant_name: str | None = None,
    category: str | None = None,
    analysis_status: str = "done",
    note: str | None = None,
    photo_count: int = 0,
) -> dict:
    """테스트용 다이어리 데이터 생성"""
    if diary_date is None:
        diary_date = datetime(2026, 1, 19, 12, 0, tzinfo=UTC)

    return {
        "user_id": user_id,
        "diary_date": diary_date,
        "time_type": time_type,
        "restaurant_name": restaurant_name,
        "restaurant_url": None,
        "road_address": None,
        "category": category,
        "analysis_status": analysis_status,
        "cover_photo_id": None,
        "note": note,
        "tags": [],
        "photo_count": photo_count,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deleted_at": None,
    }


def create_photo_data(
    diary_id: int,
    image_url: str = "https://example.com/photo.jpg",
    taken_at: datetime | None = None,
) -> dict:
    """테스트용 사진 데이터 생성"""
    return {
        "diary_id": diary_id,
        "image_url": image_url,
        "taken_at": taken_at,
        "taken_location": None,
        # Photo 모델은 datetime.utcnow를 사용하므로 timezone-naive로 생성
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


def create_diary_analysis_data(
    diary_id: int,
    restaurant_candidates: list | None = None,
    category_candidates: list | None = None,
    menu_candidates: list | None = None,
) -> dict:
    """테스트용 다이어리 분석 데이터 생성"""
    if restaurant_candidates is None:
        restaurant_candidates = [
            {"name": "맛집", "confidence": 0.9, "address": "서울시 강남구"},
            {"name": "식당", "confidence": 0.7, "address": "서울시 서초구"},
        ]
    if category_candidates is None:
        # category_candidates는 문자열 리스트여야 함
        category_candidates = ["한식", "일식"]
    if menu_candidates is None:
        # menu_candidates는 문자열 리스트여야 함
        menu_candidates = ["김치찌개", "된장찌개"]

    return {
        "diary_id": diary_id,
        "restaurant_candidates": restaurant_candidates,
        "category_candidates": category_candidates,
        "menu_candidates": menu_candidates,
        # DiaryAnalysis 모델은 datetime.utcnow를 사용하므로 timezone-naive로 생성
        "created_at": datetime.utcnow(),
    }


def create_multiple_diaries_by_date(
    user_id: UUID,
    dates: list[tuple[str, str]],  # [(date_str, time_type), ...]
) -> list[dict]:
    """
    여러 날짜의 다이어리 데이터를 생성

    Args:
        user_id: 사용자 ID
        dates: [("2026-01-19", "lunch"), ("2026-01-20", "dinner"), ...]

    Returns:
        다이어리 데이터 리스트
    """
    diaries = []
    for date_str, time_type in dates:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        diary_date = datetime(
            date_obj.year, date_obj.month, date_obj.day, 12, 0, tzinfo=UTC
        )
        diaries.append(
            create_diary_data(
                user_id=user_id,
                diary_date=diary_date,
                time_type=time_type,
                restaurant_name=f"식당 {len(diaries) + 1}",
                category="한식",
                photo_count=2,
            )
        )
    return diaries
