"""Photo 라우터"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.schemas.photo import BatchUploadResponse, PhotoUploadResult
from app.services.photo_service import (
    batch_upload_photos as batch_upload_photos_service,
)

router = APIRouter(prefix="/photos", tags=["photos"])


@router.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload_photos(
    date: Annotated[str, Form(description="대상 날짜 (YYYY-MM-DD)")],
    photos: Annotated[list[UploadFile], File(description="업로드할 이미지 파일들")],
    test_mode: Annotated[
        bool, Query(description="테스트 모드 (mock 데이터 반환)")
    ] = False,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    여러 사진을 한 번에 업로드하고 분석합니다.

    **처리 과정:**
    1. 이미지 파일 저장
    2. EXIF 파싱 (촬영 시간, GPS)
    3. 시간대별 끼니 분류 (아침/점심/저녁/간식)
    4. 다이어리 자동 생성/연결
    5. LLM 이미지 분석 (병렬 처리)
    6. GPS 기반 주변 식당 검색

    **응답 시간:** 약 5-10초 (사진 개수와 무관하게 병렬 처리)

    **test_mode=true:** mock 데이터 즉시 응답 (LLM 호출 없음)
    """
    # test_mode일 경우 mock 데이터 반환
    if test_mode:
        return _get_mock_batch_upload_response(len(photos))

    # 날짜 문자열을 date 객체로 변환
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        ) from err

    # 파일이 없는 경우
    if not photos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No photos provided",
        )

    # 파일 형식 검증
    for photo in photos:
        if not photo.content_type or not photo.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type: {photo.content_type}. "
                "Only images are allowed.",
            )

    # 배치 업로드 + 분석 처리
    results = await batch_upload_photos_service(
        db=db,
        user_id=user_id,
        target_date=target_date,
        files=photos,
    )

    return BatchUploadResponse(results=results)


# ========================================
# Mock 데이터 생성 함수
# ========================================


def _get_mock_batch_upload_response(photo_count: int) -> BatchUploadResponse:
    """test_mode용 mock 배치 업로드 응답 생성"""
    results = []

    for i in range(photo_count):
        # 다양한 시간대 시뮬레이션
        time_types = ["breakfast", "lunch", "dinner", "snack"]
        time_type = time_types[i % len(time_types)]

        # 모두 processing 상태로 반환 (즉시 응답이므로)
        results.append(
            PhotoUploadResult(
                photo_id=100 + i,
                diary_id=20 + (i // 2),  # 2개씩 같은 다이어리로 묶음
                time_type=time_type,
                image_url=f"https://picsum.photos/seed/mock{i}/400/300",
                analysis_status="processing",  # 비동기 방식이므로 항상 processing
            )
        )

    return BatchUploadResponse(results=results)
