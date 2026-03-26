"""Diary 라우터 test_mode용 mock 데이터"""

from datetime import date, datetime
from uuid import UUID

from app.schemas.diary import DiaryWithPhotos, PhotoEntry, PhotoInDiary

DATE_RANGE_RESPONSE_EXAMPLE = {
    "2026-01-15": {
        "photos": [
            {
                "url": "https://example.com/photos/1.jpg",
                "diary_date": "2026-01-15T12:30:00",
                "road_address": "서울 중구 명동길 29",
            },
            {
                "url": "https://example.com/photos/2.jpg",
                "diary_date": "2026-01-15T12:30:00",
                "road_address": "서울 중구 명동길 29",
            },
        ]
    },
    "2026-01-16": {"photos": []},
    "2026-01-17": {
        "photos": [
            {
                "url": "https://example.com/photos/3.jpg",
                "diary_date": "2026-01-17T19:00:00",
                "road_address": "서울 강남구 테헤란로 152",
            }
        ]
    },
}

_MOCK_USER_ID = UUID("e435a643-a6c8-49ab-b14f-6dc4ae5af7be")

# (name, map_url, address, category, tags)
_MOCK_RESTAURANTS = [
    (
        "명동교자",
        "https://place.map.kakao.com/477096726",
        "서울 중구 명동길 29",
        "korean",
        ["칼국수", "만두"],
    ),
    (
        "스시히로바",
        "https://place.map.kakao.com/12345678",
        "서울 강남구 테헤란로 152",
        "japanese",
        ["사시미", "라멘"],
    ),
    (
        "투썸플레이스",
        "https://place.map.kakao.com/23456789",
        "서울 마포구 월드컵북로 396",
        "etc",
        ["아메리카노", "크로와상"],
    ),
    (
        "버거킹",
        "https://place.map.kakao.com/34567890",
        "서울 종로구 종로 1",
        "etc",
        ["와퍼", "감자튀김"],
    ),
    (
        "봉피양",
        "https://place.map.kakao.com/45678901",
        "서울 서초구 서초대로 396",
        "korean",
        ["평양냉면", "불고기"],
    ),
]

_MOCK_TIME_TYPES = ["breakfast", "lunch", "dinner", "snack"]

# bucket(seed % 5) → 사진 수 (0 = 빈 날짜)
_BUCKET_TO_PHOTO_COUNT = [0, 1, 2, 3, 5]


def _mock_photos(seed: int, count: int, base_id: int) -> list[PhotoInDiary]:
    return [
        PhotoInDiary(
            photo_id=base_id + i,
            image_url=f"https://picsum.photos/seed/{seed}{chr(97 + i)}/400/300",
        )
        for i in range(count)
    ]


def get_mock_diaries_response(start_date: date, end_date: date) -> dict:
    """GET /diaries test_mode용 mock 응답 - DiariesByDateResponse 구조"""
    diaries = []
    current = start_date
    diary_id = int(current.strftime("%Y%m%d")) % 1000

    while current <= end_date:
        seed = int(current.strftime("%Y%m%d"))
        photo_count = _BUCKET_TO_PHOTO_COUNT[seed % 5]

        if photo_count > 0:
            name, url, address, category, tags = _MOCK_RESTAURANTS[
                seed % len(_MOCK_RESTAURANTS)
            ]
            time_type = _MOCK_TIME_TYPES[seed % len(_MOCK_TIME_TYPES)]
            photos = _mock_photos(seed, photo_count, diary_id * 10)
            noon = datetime(current.year, current.month, current.day, 12, 0)
            diaries.append(
                DiaryWithPhotos(
                    id=diary_id,
                    user_id=_MOCK_USER_ID,
                    diary_date=current,
                    time_type=time_type,
                    analysis_status="done",
                    restaurant_name=name,
                    restaurant_url=url,
                    road_address=address,
                    category=category,
                    cover_photo_id=diary_id * 10,
                    cover_photo_url=f"https://picsum.photos/seed/{seed}a/400/300",
                    note=None,
                    tags=tags,
                    photo_count=photo_count,
                    created_at=noon,
                    updated_at=noon,
                    photos=photos,
                )
            )

        diary_id += 1
        current = date.fromordinal(current.toordinal() + 1)

    return {"diaries": diaries}


def get_mock_date_range_response(start_date: date, end_date: date) -> dict[str, dict]:
    """GET /diaries/summary test_mode용 mock 응답 - 날짜별 사진 목록 반환"""
    result = {}
    current = start_date

    while current <= end_date:
        seed = int(current.strftime("%Y%m%d"))
        photo_count = _BUCKET_TO_PHOTO_COUNT[seed % 5]
        _, _, address, _, _ = _MOCK_RESTAURANTS[seed % len(_MOCK_RESTAURANTS)]
        noon = datetime(current.year, current.month, current.day, 12, 0)
        photos = [
            PhotoEntry(
                url=f"https://picsum.photos/seed/{seed}{chr(97 + i)}/400/300",
                diary_date=noon,
                road_address=address if photo_count > 0 else None,
            )
            for i in range(photo_count)
        ]
        result[current.isoformat()] = {"photos": photos}
        current = date.fromordinal(current.toordinal() + 1)

    return result


def get_mock_diary_detail(diary_id: int) -> DiaryWithPhotos:
    """GET /diaries/{diary_id} test_mode용 mock 응답"""
    if diary_id == 12:
        return DiaryWithPhotos(
            id=12,
            user_id=_MOCK_USER_ID,
            diary_date=date(2026, 1, 19),
            time_type="lunch",
            analysis_status="done",
            restaurant_name="명동교자",
            restaurant_url="https://place.map.kakao.com/477096726",
            road_address="서울 중구 명동길 29",
            category="korean",
            cover_photo_id=101,
            cover_photo_url="https://picsum.photos/seed/diary12/400/300",
            note="칼국수 맛집 발견!",
            tags=["칼국수", "만두"],
            photo_count=3,
            created_at=datetime(2026, 1, 19, 12, 40),
            updated_at=datetime(2026, 1, 19, 12, 45),
            photos=_mock_photos(20260119, 3, 101),
        )
    if diary_id == 10:
        return DiaryWithPhotos(
            id=10,
            user_id=_MOCK_USER_ID,
            diary_date=date(2026, 1, 18),
            time_type="dinner",
            analysis_status="processing",
            restaurant_name=None,
            restaurant_url=None,
            road_address=None,
            category=None,
            cover_photo_id=95,
            cover_photo_url="https://picsum.photos/seed/diary10/400/300",
            note=None,
            tags=[],
            photo_count=2,
            created_at=datetime(2026, 1, 18, 19, 0),
            updated_at=datetime(2026, 1, 18, 19, 0),
            photos=[
                PhotoInDiary(
                    photo_id=95,
                    image_url="https://picsum.photos/seed/photo95/400/300",
                ),
                PhotoInDiary(
                    photo_id=96,
                    image_url="https://picsum.photos/seed/photo96/400/300",
                ),
            ],
        )
    # 기본값
    return DiaryWithPhotos(
        id=diary_id,
        user_id=_MOCK_USER_ID,
        diary_date=date(2026, 1, 20),
        time_type="breakfast",
        analysis_status="done",
        restaurant_name="스타벅스",
        restaurant_url="https://place.map.kakao.com/34567890",
        road_address="서울 강남구 역삼동 123-45",
        category="etc",
        cover_photo_id=200,
        cover_photo_url="https://picsum.photos/seed/default/400/300",
        note="모닝 커피",
        tags=["아메리카노"],
        photo_count=1,
        created_at=datetime(2026, 1, 20, 8, 0),
        updated_at=datetime(2026, 1, 20, 8, 5),
        photos=_mock_photos(20260120, 1, 200),
    )
