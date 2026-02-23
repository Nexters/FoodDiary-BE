"""Diary 라우터"""

import logging
from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.models.diary import Diary
from app.schemas.diary import (
    AddDiaryPhotosResponse,
    DatePhotosEntry,
    DiariesByDateResponse,
    DiaryAnalysisResponse,
    DiaryBlogTextResponse,
    DiaryUpdate,
    DiaryWithPhotos,
    PhotoEntry,
    PhotoInDiary,
)
from app.services import diary_service, llm_service
from app.services.diary_service import _build_tags, _merge_date_with_cover_taken_at

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diaries", tags=["diaries"])


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


@router.get("", response_model=DiariesByDateResponse)
async def get_diaries_by_date_range(
    start_date_str: Annotated[
        str,
        Query(alias="start_date", description="시작 날짜 (YYYY-MM-DD)"),
    ],
    end_date_str: Annotated[
        str,
        Query(alias="end_date", description="종료 날짜 (YYYY-MM-DD)"),
    ],
    test_mode: Annotated[
        bool, Query(description="테스트 모드 (mock 데이터 반환)")
    ] = False,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    날짜 범위로 다이어리 상세 목록 조회

    **파라미터:**
    - `start_date`: 시작 날짜 (YYYY-MM-DD, 필수)
    - `end_date`: 종료 날짜 (YYYY-MM-DD, 필수, start_date와 같으면 단일 날짜 조회)

    **응답:**
    - 해당 범위의 다이어리 목록 (사진, 분석 상태 등 전체 필드 포함)
    - 최대 42일 범위 제한
    """
    if test_mode:
        try:
            start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return {"diaries": []}
        return _get_mock_diaries_response(start, end)

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        ) from err

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    if (end_date - start_date).days > 42:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range must be within 42 days",
        )

    diaries = await diary_service.get_diaries_by_date_range(
        db=db,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )
    return {"diaries": [_build_diary_with_photos(d) for d in diaries]}


@router.get(
    "/summary",
    response_model=dict[str, DatePhotosEntry],
    responses={
        200: {
            "description": (
                "날짜별 사진 목록 (키: YYYY-MM-DD, 값: photos 배열 - "
                "각 사진의 url/diary_date/road_address 포함)"
            ),
            "content": {
                "application/json": {
                    "example": DATE_RANGE_RESPONSE_EXAMPLE,
                }
            },
        }
    },
)
async def get_diaries_summary_by_date_range(
    start_date_str: Annotated[
        str,
        Query(alias="start_date", description="시작 날짜 (YYYY-MM-DD)"),
    ],
    end_date_str: Annotated[
        str,
        Query(alias="end_date", description="종료 날짜 (YYYY-MM-DD)"),
    ],
    test_mode: Annotated[
        bool, Query(description="테스트 모드 (mock 데이터 반환)")
    ] = False,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    날짜 범위로 다이어리 사진 URL 목록 조회 (캘린더 뷰용)

    **파라미터:**
    - `start_date`: 시작 날짜 (YYYY-MM-DD, 필수)
    - `end_date`: 종료 날짜 (YYYY-MM-DD, 필수)

    **응답:**
    - 날짜별 사진 URL 목록만 반환
    - 다이어리가 없는 날짜도 빈 배열로 포함
    - 최대 42일 범위 제한
    """
    if test_mode:
        try:
            start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            return _get_mock_date_range_response(start, end)
        except ValueError:
            pass
        return _get_mock_date_range_response(date(2026, 2, 14), date(2026, 2, 16))

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        ) from err

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    if (end_date - start_date).days > 42:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range must be within 42 days",
        )

    diaries = await diary_service.get_diaries_by_date_range(
        db=db,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )
    return _build_date_photos_response(start_date, end_date, diaries)


@router.get("/{diary_id}", response_model=DiaryWithPhotos)
async def get_diary_by_id(
    diary_id: int,
    test_mode: Annotated[
        bool, Query(description="테스트 모드 (mock 데이터 반환)")
    ] = False,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    다이어리 ID로 단일 조회

    **사용 시나리오:**
    1. FCM 푸시로 diary_id 수신
    2. GET /diaries/{diary_id}로 상세 조회
    3. analysis_status: "done" 확인 후 데이터 표시
    """
    # test_mode일 경우 mock 데이터 반환
    if test_mode:
        return _get_mock_diary_detail(diary_id)

    diary = await diary_service.get_diary_by_id(
        db=db, user_id=user_id, diary_id=diary_id
    )
    if diary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diary not found or you don't have access.",
        )
    return diary


@router.get("/{diary_id}/suggestions", response_model=DiaryAnalysisResponse)
async def get_diary_suggestions(
    diary_id: int,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    다이어리 분석 제안 조회 (식당, 카테고리, 메뉴 후보)

    "이 식당을 찾고 계신가요?" 화면에서 사용
    DiaryAnalysis의 restaurant_candidates, category_candidates, menu_candidates 반환
    """
    analysis = await diary_service.get_diary_analysis(
        db=db, user_id=user_id, diary_id=diary_id
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found or diary doesn't exist.",
        )
    return analysis


@router.get("/{diary_id}/blog-text", response_model=DiaryBlogTextResponse)
async def get_diary_blog_text(
    diary_id: int,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    다이어리 정보로 블로그 공유용 텍스트 생성

    "블로그에 공유할 텍스트 복사" 버튼 시 호출.
    식당/메뉴/메모를 바탕으로 네이버 맛집 블로그 스타일 본문을 생성합니다.
    """
    diary = await diary_service.get_diary_by_id(
        db=db, user_id=user_id, diary_id=diary_id
    )
    if diary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diary not found or you don't have access.",
        )

    diary_info = {
        "restaurant_name": diary.restaurant_name,
        "road_address": diary.road_address,
        "category": diary.category,
        "note": diary.note,
        "tags": diary.tags,
        "diary_date": diary.diary_date.isoformat(),
        "time_type_ko": llm_service.TIME_TYPE_KO.get(diary.time_type, diary.time_type),
        "restaurant_url": diary.restaurant_url,
    }

    try:
        blog_text = await llm_service.generate_blog_text(diary_info)
    except Exception as e:
        logger.exception("블로그 텍스트 생성 실패: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Blog text generation failed. Please try again later.",
        ) from e

    return DiaryBlogTextResponse(blog_text=blog_text)


@router.patch("/{diary_id}", response_model=DiaryWithPhotos)
async def update_diary(
    diary_id: int,
    body: DiaryUpdate,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    다이어리 수정 (수정 화면 "저장").

    전달된 필드만 반영. photo_ids가 있으면 해당 ID만 유지·순서 반영, 나머지 사진 삭제.
    """
    diary = await diary_service.update_diary(
        db=db, user_id=user_id, diary_id=diary_id, body=body
    )
    if diary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diary not found or you don't have access.",
        )
    return diary


@router.post(
    "/{diary_id}/photos",
    response_model=AddDiaryPhotosResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_diary_photos(
    diary_id: int,
    photos: Annotated[list[UploadFile], File(description="추가할 이미지 파일들")],
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    기존 다이어리에 사진 추가 (수정 화면에서 + 버튼).

    multipart/form-data로 이미지 1장 이상. 새로 생성된 photo_id 목록 반환.
    저장 시 PATCH의 photo_ids에 기존 id + 이 응답의 photo_ids를 넣으면 됨.

    **제한사항:**
    - 다이어리당 최대 10개의 사진만 업로드 가능
    """
    if not photos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No photos provided",
        )
    for photo in photos:
        if not photo.content_type or not photo.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image files are allowed.",
            )
    try:
        photo_ids = await diary_service.add_photos_to_diary(
            db=db, user_id=user_id, diary_id=diary_id, files=photos
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    if photo_ids is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diary not found or you don't have access.",
        )
    return AddDiaryPhotosResponse(photo_ids=photo_ids)


@router.delete("/{diary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diary(
    diary_id: int,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    다이어리 전체 삭제 (수정 화면 "삭제" 버튼).
    소프트 삭제(deleted_at 설정). 소유자만 가능.
    """
    deleted = await diary_service.delete_diary(
        db=db, user_id=user_id, diary_id=diary_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diary not found or you don't have access.",
        )


# ========================================
# 응답 변환 헬퍼 함수들
# ========================================


def _build_diary_with_photos(diary: Diary) -> DiaryWithPhotos:
    status = diary.analysis_status or "done"
    cover_photo_url = diary.get_cover_photo_url(settings.IMAGE_BASE_URL)
    photos = [
        PhotoInDiary(
            photo_id=p.id,
            image_url=p.get_full_url(settings.IMAGE_BASE_URL),
            analysis_status=status,
        )
        for p in sorted(diary.photos, key=lambda x: x.id)
    ]
    return DiaryWithPhotos(
        id=diary.id,
        user_id=diary.user_id,
        diary_date=_merge_date_with_cover_taken_at(diary),
        time_type=diary.time_type,
        analysis_status=status,
        restaurant_name=diary.restaurant_name,
        restaurant_url=diary.restaurant_url,
        road_address=diary.road_address,
        category=diary.category,
        cover_photo_id=diary.cover_photo_id,
        cover_photo_url=cover_photo_url,
        note=diary.note,
        tags=_build_tags(diary),
        photo_count=diary.photo_count,
        created_at=diary.created_at,
        updated_at=diary.updated_at,
        photos=photos,
    )


def _build_date_photos_response(
    start_date: date, end_date: date, diaries: list[Diary]
) -> dict[str, dict]:
    response: dict[str, dict] = {}
    cur = start_date
    while cur <= end_date:
        response[cur.isoformat()] = {"photos": []}
        cur = cur + timedelta(days=1)

    for diary in diaries:
        date_key = diary.diary_date.date().isoformat()
        if date_key not in response:
            response[date_key] = {"photos": []}
        diary_date = _merge_date_with_cover_taken_at(diary)
        for p in sorted(diary.photos, key=lambda x: x.id):
            response[date_key]["photos"].append(
                PhotoEntry(
                    url=p.get_full_url(settings.IMAGE_BASE_URL),
                    diary_date=diary_date,
                    road_address=diary.road_address,
                )
            )

    return response


# ========================================
# Mock 데이터 생성 함수들
# ========================================

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
            analysis_status="done",
        )
        for i in range(count)
    ]


def _get_mock_diaries_response(start_date: date, end_date: date) -> dict:
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


def _get_mock_date_range_response(start_date: date, end_date: date) -> dict[str, dict]:
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


def _get_mock_diary_detail(diary_id: int) -> DiaryWithPhotos:
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
                    analysis_status="processing",
                ),
                PhotoInDiary(
                    photo_id=96,
                    image_url="https://picsum.photos/seed/photo96/400/300",
                    analysis_status="processing",
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
