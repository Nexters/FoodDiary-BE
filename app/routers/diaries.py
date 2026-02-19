"""Diary 라우터"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.schemas.diary import (
    AddDiaryPhotosResponse,
    DatePhotosEntry,
    DiariesByDateResponse,
    DiaryAnalysisResponse,
    DiaryUpdate,
    DiaryWithPhotos,
    PhotoInDiary,
)
from app.services import diary_service

router = APIRouter(prefix="/diaries", tags=["diaries"])


DATE_RANGE_RESPONSE_EXAMPLE = {
    "2026-01-15": {
        "photos": [
            "https://example.com/photos/1.jpg",
            "https://example.com/photos/2.jpg",
        ]
    },
    "2026-01-16": {"photos": []},
    "2026-01-17": {"photos": ["https://example.com/photos/3.jpg"]},
}


@router.get(
    "",
    response_model=dict[str, DatePhotosEntry],
    responses={
        200: {
            "description": "날짜별 사진 URL 목록 (키: YYYY-MM-DD, 값: photos 배열)",
            "content": {
                "application/json": {
                    "example": DATE_RANGE_RESPONSE_EXAMPLE,
                }
            },
        }
    },
)
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
    날짜 범위로 다이어리 사진 목록 조회 (캘린더 뷰용)

    **파라미터:**
    - `start_date`: 시작 날짜 (YYYY-MM-DD, 필수)
    - `end_date`: 종료 날짜 (YYYY-MM-DD, 필수)

    **응답:**
    - 날짜별 사진 URL 목록
    - 다이어리가 없는 날짜도 빈 배열로 포함
    - 최대 31일 범위 제한
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

    if (end_date - start_date).days > 31:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range must be within 31 days",
        )

    return await diary_service.get_diaries_by_date_range(
        db=db,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/daily", response_model=DiariesByDateResponse)
async def get_diaries_by_date(
    date_str: Annotated[
        str,
        Query(alias="date", description="조회할 날짜 (YYYY-MM-DD)"),
    ],
    test_mode: Annotated[
        bool, Query(description="테스트 모드 (mock 데이터 반환)")
    ] = False,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    특정 날짜의 다이어리 목록 조회 (일간 뷰용)

    **파라미터:**
    - `date`: 조회할 날짜 (YYYY-MM-DD, 필수)

    **응답:**
    - 해당 날짜의 다이어리 목록 (사진, 분석 상태 등 전체 필드 포함)
    """
    if test_mode:
        try:
            query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            return _get_mock_daily_response(query_date)
        except ValueError:
            pass
        return _get_mock_daily_response(date(2026, 2, 14))

    try:
        query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        ) from err

    return await diary_service.get_diaries_by_date(
        db=db,
        user_id=user_id,
        query_date=query_date,
    )


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
# Mock 데이터 생성 함수들
# ========================================


def _get_mock_date_range_response(start_date: date, end_date: date) -> dict[str, dict]:
    """범위 조회 mock 응답 생성 - 날짜별 사진 URL 목록만 반환"""
    result = {}
    current = start_date

    while current <= end_date:
        date_str = current.isoformat()
        day = current.day

        if day % 3 == 1:  # 점심 2장 + 저녁 3장
            result[date_str] = {
                "photos": [
                    f"https://picsum.photos/seed/photo{day}a/400/300",
                    f"https://picsum.photos/seed/photo{day}b/400/300",
                    f"https://picsum.photos/seed/photo{day}c/400/300",
                    f"https://picsum.photos/seed/photo{day}d/400/300",
                    f"https://picsum.photos/seed/photo{day}e/400/300",
                ]
            }
        elif day % 3 == 2:  # 아침 1장
            result[date_str] = {
                "photos": [
                    f"https://picsum.photos/seed/photo{day}f/400/300",
                ]
            }
        else:  # 빈 날짜
            result[date_str] = {"photos": []}

        current = date.fromordinal(current.toordinal() + 1)

    return result


def _get_mock_daily_response(query_date: date) -> dict:
    """일간 조회 mock 응답 생성 - 해당 날짜의 다이어리 목록 전체 필드 반환"""
    mock_user_id = UUID("e435a643-a6c8-49ab-b14f-6dc4ae5af7be")
    date_str = query_date.isoformat()
    day = query_date.day

    if day % 3 == 1:
        is_processing = day in [19, 25]
        diaries = [
            {
                "id": day * 10,
                "user_id": mock_user_id,
                "diary_date": date_str,
                "time_type": "lunch",
                "analysis_status": "processing" if is_processing else "done",
                "restaurant_name": None if is_processing else "명동교자",
                "restaurant_url": (
                    None if is_processing else "https://place.map.kakao.com/477096726"
                ),
                "road_address": None if is_processing else "서울 중구 명동길 29",
                "category": None if is_processing else "한식",
                "cover_photo_id": day * 10 + 1,
                "cover_photo_url": f"https://picsum.photos/seed/lunch{day}/400/300",
                "note": None if is_processing else "칼국수가 정말 맛있었다",
                "tags": [] if is_processing else ["칼국수", "만두"],
                "photo_count": 2,
                "created_at": f"{date_str}T12:00:00",
                "updated_at": f"{date_str}T12:05:30",
                "photos": [
                    {
                        "photo_id": day * 10 + 1,
                        "image_url": f"https://picsum.photos/seed/photo{day}a/400/300",
                        "analysis_status": "processing" if is_processing else "done",
                    },
                    {
                        "photo_id": day * 10 + 2,
                        "image_url": f"https://picsum.photos/seed/photo{day}b/400/300",
                        "analysis_status": "processing" if is_processing else "done",
                    },
                ],
            },
            {
                "id": day * 10 + 5,
                "user_id": mock_user_id,
                "diary_date": date_str,
                "time_type": "dinner",
                "analysis_status": "done",
                "restaurant_name": "스시히로바",
                "restaurant_url": "https://place.map.kakao.com/12345678",
                "road_address": "서울 강남구 테헤란로 152",
                "category": "일식",
                "cover_photo_id": day * 10 + 6,
                "cover_photo_url": f"https://picsum.photos/seed/dinner{day}/400/300",
                "note": "신선한 회가 일품",
                "tags": ["사시미", "라멘"],
                "photo_count": 3,
                "created_at": f"{date_str}T19:00:00",
                "updated_at": f"{date_str}T19:10:00",
                "photos": [
                    {
                        "photo_id": day * 10 + 6,
                        "image_url": f"https://picsum.photos/seed/photo{day}c/400/300",
                        "analysis_status": "done",
                    },
                    {
                        "photo_id": day * 10 + 7,
                        "image_url": f"https://picsum.photos/seed/photo{day}d/400/300",
                        "analysis_status": "done",
                    },
                    {
                        "photo_id": day * 10 + 8,
                        "image_url": f"https://picsum.photos/seed/photo{day}e/400/300",
                        "analysis_status": "done",
                    },
                ],
            },
        ]
    elif day % 3 == 2:
        diaries = [
            {
                "id": day * 10,
                "user_id": mock_user_id,
                "diary_date": date_str,
                "time_type": "breakfast",
                "analysis_status": "done",
                "restaurant_name": "투썸플레이스",
                "restaurant_url": "https://place.map.kakao.com/23456789",
                "road_address": "서울 마포구 월드컵북로 396",
                "category": "카페",
                "cover_photo_id": day * 10 + 1,
                "cover_photo_url": f"https://picsum.photos/seed/breakfast{day}/400/300",
                "note": "커피 한 잔의 여유",
                "tags": ["아메리카노", "크로와상"],
                "photo_count": 1,
                "created_at": f"{date_str}T08:30:00",
                "updated_at": f"{date_str}T08:32:00",
                "photos": [
                    {
                        "photo_id": day * 10 + 1,
                        "image_url": f"https://picsum.photos/seed/photo{day}f/400/300",
                        "analysis_status": "done",
                    }
                ],
            }
        ]
    else:
        diaries = []

    return {"diaries": diaries}


def _get_mock_diary_detail(diary_id: int) -> DiaryWithPhotos:
    """mock 다이어리 상세 응답 생성"""
    mock_user_id = UUID("e435a643-a6c8-49ab-b14f-6dc4ae5af7be")

    # diary_id에 따라 다른 mock 데이터 반환
    if diary_id == 12:
        # 분석 완료된 다이어리
        return DiaryWithPhotos(
            id=12,
            user_id=mock_user_id,
            diary_date=date(2026, 1, 19),
            time_type="lunch",
            analysis_status="done",
            restaurant_name="명동교자",
            restaurant_url="https://place.map.kakao.com/477096726",
            road_address="서울 중구 명동길 29",
            category="한식",
            cover_photo_id=101,
            cover_photo_url="https://picsum.photos/seed/diary12/400/300",
            note="칼국수 맛집 발견!",
            tags=["칼국수", "만두"],
            photo_count=3,
            created_at=datetime(2026, 1, 19, 12, 40, 0),
            updated_at=datetime(2026, 1, 19, 12, 45, 30),
            photos=[
                PhotoInDiary(
                    photo_id=101,
                    image_url="https://picsum.photos/seed/photo101/400/300",
                    analysis_status="done",
                ),
                PhotoInDiary(
                    photo_id=102,
                    image_url="https://picsum.photos/seed/photo102/400/300",
                    analysis_status="done",
                ),
                PhotoInDiary(
                    photo_id=103,
                    image_url="https://picsum.photos/seed/photo103/400/300",
                    analysis_status="done",
                ),
            ],
        )
    if diary_id == 10:
        # 분석 중인 다이어리
        return DiaryWithPhotos(
            id=10,
            user_id=mock_user_id,
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
            created_at=datetime(2026, 1, 18, 19, 0, 0),
            updated_at=datetime(2026, 1, 18, 19, 0, 0),
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
    # 기본값 (분석 완료)
    return DiaryWithPhotos(
        id=diary_id,
        user_id=mock_user_id,
        diary_date=date(2026, 1, 20),
        time_type="breakfast",
        analysis_status="done",
        restaurant_name="스타벅스",
        restaurant_url="https://place.map.kakao.com/34567890",
        road_address="서울 강남구 역삼동 123-45",
        category="카페",
        cover_photo_id=200,
        cover_photo_url="https://picsum.photos/seed/default/400/300",
        note="모닝 커피",
        tags=["아메리카노"],
        photo_count=1,
        created_at=datetime(2026, 1, 20, 8, 0, 0),
        updated_at=datetime(2026, 1, 20, 8, 5, 0),
        photos=[
            PhotoInDiary(
                photo_id=200,
                image_url="https://picsum.photos/seed/photo200/400/300",
                analysis_status="done",
            )
        ],
    )
