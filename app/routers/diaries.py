"""Diary 라우터"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.schemas.diary import DiaryWithPhotos, PhotoInDiary

router = APIRouter(prefix="/diaries", tags=["diaries"])


@router.get("", response_model=dict[str, dict])
async def get_diaries_by_date_range(
    date_str: Annotated[
        str | None,
        Query(alias="date", description="특정 날짜 조회 (YYYY-MM-DD)"),
    ] = None,
    start_date_str: Annotated[
        str | None,
        Query(alias="start_date", description="시작 날짜 (YYYY-MM-DD)"),
    ] = None,
    end_date_str: Annotated[
        str | None,
        Query(alias="end_date", description="종료 날짜 (YYYY-MM-DD)"),
    ] = None,
    test_mode: Annotated[
        bool, Query(description="테스트 모드 (mock 데이터 반환)")
    ] = False,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    날짜 범위로 다이어리 목록 조회

    **파라미터 조합:**
    - `date`: 특정 날짜 조회 (YYYY-MM-DD)
    - `start_date` + `end_date`: 기간 조회 (YYYY-MM-DD)

    ⚠️ `date` 또는 `start_date + end_date` 중 하나는 필수

    **응답:**
    - 날짜별로 그룹핑된 딕셔너리
    - 다이어리가 없는 날짜도 빈 배열로 포함
    """
    # test_mode일 경우 mock 데이터 반환
    if test_mode:
        # 날짜 파싱 (에러 처리 포함)
        try:
            if date_str:
                query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                return _get_mock_diaries_response(query_date, query_date)
            if start_date_str and end_date_str:
                start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                return _get_mock_diaries_response(start, end)
        except ValueError:
            # 날짜 파싱 실패 시 기본 mock 데이터 반환
            pass
        return _get_mock_diaries_response(date(2026, 1, 19), date(2026, 1, 19))

    # 파라미터 검증
    if date_str and (start_date_str or end_date_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot use 'date' with 'start_date' or 'end_date'",
        )

    if not date_str and not (start_date_str and end_date_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'date' or both 'start_date' and 'end_date' are required",
        )

    # 날짜 파싱
    try:
        if date_str:
            query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_date = query_date
            end_date = query_date
        else:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        ) from err

    # 날짜 범위 검증
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    # 최대 31일 제한
    if (end_date - start_date).days > 31:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range must be within 31 days",
        )

    # TODO: 실제 DB 조회 로직 구현
    # 임시로 빈 응답 반환
    result = {}
    current = start_date
    while current <= end_date:
        result[current.isoformat()] = {"diaries": []}
        current = date.fromordinal(current.toordinal() + 1)

    return result


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

    # TODO: 실제 DB 조회 로직 구현
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Diary {diary_id} not found",
    )


# ========================================
# Mock 데이터 생성 함수들
# ========================================


def _get_mock_diaries_response(start_date: date, end_date: date) -> dict[str, dict]:
    """mock 다이어리 목록 응답 생성 (날짜 범위 기반)"""
    mock_user_id = UUID("e435a643-a6c8-49ab-b14f-6dc4ae5af7be")

    result = {}
    current = start_date

    # 날짜 범위만큼 반복
    while current <= end_date:
        date_str = current.isoformat()

        # 특정 날짜에만 다이어리 데이터 생성 (랜덤하게)
        # 날짜의 일(day)을 기준으로 패턴 생성
        day = current.day

        if day % 3 == 1:  # 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31일
            # 점심 + 저녁 2개
            # 19일과 25일은 processing 상태로
            is_processing = day in [19, 25]

            result[date_str] = {
                "diaries": [
                    {
                        "id": day * 10,
                        "user_id": mock_user_id,
                        "diary_date": date_str,
                        "time_type": "lunch",
                        "analysis_status": "processing" if is_processing else "done",
                        "restaurant_name": None if is_processing else "명동교자",
                        "restaurant_url": (
                            None
                            if is_processing
                            else "https://place.map.kakao.com/477096726"
                        ),
                        "road_address": (
                            None if is_processing else "서울 중구 명동길 29"
                        ),
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
                                "analysis_status": (
                                    "processing" if is_processing else "done"
                                ),
                            },
                            {
                                "photo_id": day * 10 + 2,
                                "image_url": f"https://picsum.photos/seed/photo{day}b/400/300",
                                "analysis_status": (
                                    "processing" if is_processing else "done"
                                ),
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
            }
        elif day % 3 == 2:  # 2, 5, 8, 11, 14, 17, 20, 23, 26, 29일
            # 아침만 1개
            result[date_str] = {
                "diaries": [
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
            }
        else:  # 3, 6, 9, 12, 15, 18, 21, 24, 27, 30일
            # 빈 날짜
            result[date_str] = {"diaries": []}

        current = date.fromordinal(current.toordinal() + 1)

    return result


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
