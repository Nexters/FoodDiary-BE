"""Diary 라우터"""

import logging
from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session, get_session_v2
from app.core.dependencies import get_current_user_id
from app.routers.diaries_mock import (
    DATE_RANGE_RESPONSE_EXAMPLE,
    get_mock_date_range_response,
    get_mock_diaries_response,
    get_mock_diary_detail,
)
from app.schemas.diary import (
    AddDiaryPhotosResponse,
    DatePhotosEntry,
    DiariesByDateResponse,
    DiaryBlogTextResponse,
    DiaryUpdate,
    DiaryWithPhotos,
    PhotoEntry,
)
from app.schemas.restaurant import RestaurantListResponse
from app.services import diary_service, llm_service
from app.usecases import diary as diary_usecase
from app.usecases import restaurant as restaurant_usecase
from app.usecases.diary import (
    DateRangeInvalidError,
    DateRangeTooLongError,
    DiaryNotFoundError,
    PhotoLimitExceededError,
    PhotoRequiredError,
)
from app.utils.timezone import utc_to_kst_naive

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diaries", tags=["diaries"])

DIARY_NOT_FOUND = "다이어리를 찾을 수 없거나 접근 권한이 없습니다."


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
    db: AsyncSession = Depends(get_session_v2),
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
        return get_mock_diaries_response(start, end)

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력하세요.",
        ) from err

    try:
        diaries = await diary_usecase.get_diaries_by_date_range(
            db, user_id, start_date, end_date
        )
    except DateRangeInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="시작 날짜는 종료 날짜보다 이전이거나 같아야 합니다.",
        ) from e
    except DateRangeTooLongError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="날짜 범위는 42일 이내여야 합니다.",
        ) from e
    return {"diaries": diaries}


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
    db: AsyncSession = Depends(get_session_v2),
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
            return get_mock_date_range_response(start, end)
        except ValueError:
            pass
        return get_mock_date_range_response(date(2026, 2, 14), date(2026, 2, 16))

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력하세요.",
        ) from err

    try:
        diaries = await diary_usecase.get_diaries_by_date_range(
            db, user_id, start_date, end_date
        )
    except DateRangeInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="시작 날짜는 종료 날짜보다 이전이거나 같아야 합니다.",
        ) from e
    except DateRangeTooLongError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="날짜 범위는 42일 이내여야 합니다.",
        ) from e
    return _build_date_photos_response(start_date, end_date, diaries)


@router.get("/{diary_id}", response_model=DiaryWithPhotos)
async def get_diary_by_id(
    diary_id: int,
    test_mode: Annotated[
        bool, Query(description="테스트 모드 (mock 데이터 반환)")
    ] = False,
    db: AsyncSession = Depends(get_session_v2),
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
        return get_mock_diary_detail(diary_id)

    try:
        return await diary_usecase.get_diary(db, user_id, diary_id)
    except DiaryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DIARY_NOT_FOUND,
        ) from e


@router.get("/{diary_id}/suggestions", response_model=RestaurantListResponse)
async def get_diary_suggestions(
    diary_id: int,
    db: AsyncSession = Depends(get_session_v2),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    다이어리 분석 제안 조회 (식당 후보 목록)

    "이 식당을 찾고 계신가요?" 화면에서 사용
    DiaryAnalysis.result의 각 후보를 restaurant 단위로 반환
    """
    restaurants = await restaurant_usecase.get_diary_restaurants(
        session=db, user_id=user_id, diary_id=diary_id
    )
    return RestaurantListResponse(restaurants=restaurants)


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
            detail=DIARY_NOT_FOUND,
        )

    diary_info = {
        "restaurant_name": diary.restaurant_name,
        "road_address": diary.road_address,
        "category": diary.category,
        "note": diary.note,
        "tags": diary.tags,
        "diary_date": utc_to_kst_naive(diary.diary_date).isoformat(),
        "time_type_ko": llm_service.TIME_TYPE_KO.get(diary.time_type, diary.time_type),
        "restaurant_url": diary.restaurant_url,
    }

    try:
        blog_text = await llm_service.generate_blog_text(diary_info)
    except Exception as e:
        logger.exception("블로그 텍스트 생성 실패: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="블로그 텍스트 생성에 실패했습니다. 잠시 후 다시 시도해주세요.",
        ) from e

    return DiaryBlogTextResponse(blog_text=blog_text)


@router.patch("/{diary_id}", response_model=DiaryWithPhotos)
async def update_diary(
    diary_id: int,
    body: DiaryUpdate,
    db: AsyncSession = Depends(get_session_v2),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    다이어리 수정 (수정 화면 "저장").

    전달된 필드만 반영. photo_ids가 있으면 해당 ID만 유지·순서 반영, 나머지 사진 삭제.
    """
    try:
        return await diary_usecase.update_diary(db, user_id, diary_id, body)
    except DiaryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DIARY_NOT_FOUND,
        ) from e
    except PhotoRequiredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="최소 1개의 사진이 필요합니다.",
        ) from e


@router.post(
    "/{diary_id}/photos",
    response_model=AddDiaryPhotosResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_diary_photos(
    diary_id: int,
    photos: Annotated[list[UploadFile], File(description="추가할 이미지 파일들")],
    db: AsyncSession = Depends(get_session_v2),
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
            detail="사진을 업로드해주세요.",
        )
    for photo in photos:
        if not photo.content_type or not photo.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미지 파일만 업로드할 수 있습니다.",
            )
    try:
        photo_ids = await diary_usecase.add_diary_photos(
            session=db, user_id=user_id, diary_id=diary_id, files=photos
        )
    except DiaryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DIARY_NOT_FOUND,
        ) from e
    except PhotoLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return AddDiaryPhotosResponse(photo_ids=photo_ids)


@router.delete("/{diary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diary(
    diary_id: int,
    db: AsyncSession = Depends(get_session_v2),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    다이어리 전체 삭제 (수정 화면 "삭제" 버튼).
    소프트 삭제(deleted_at 설정). 소유자만 가능.
    """
    try:
        await diary_usecase.delete_diary(db, user_id, diary_id)
    except DiaryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DIARY_NOT_FOUND,
        ) from e


# ========================================
# 응답 변환 헬퍼 함수들
# ========================================


def _build_date_photos_response(
    start_date: date, end_date: date, diaries: list[DiaryWithPhotos]
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
        for p in diary.photos:
            response[date_key]["photos"].append(
                PhotoEntry(
                    url=p.image_url,
                    diary_date=diary.diary_date,
                    road_address=diary.road_address,
                )
            )

    return response
