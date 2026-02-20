"""Photo 라우터"""

import logging
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.schemas.photo import BatchUploadResponse, PhotoUploadResult
from app.services.photo_service import analyze_and_notify, batch_upload_photos_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/photos", tags=["photos"])


@router.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload_photos_endpoint(
    date: Annotated[str, Form(description="대상 날짜 (YYYY-MM-DD)")],
    device_id: Annotated[str, Form(description="요청 디바이스 ID")],
    photos: Annotated[list[UploadFile], File(description="업로드할 이미지 파일들")],
    background_tasks: BackgroundTasks,
    test_mode: Annotated[
        bool, Query(description="테스트 모드 (LLM 분석을 mock 데이터로 대체)")
    ] = False,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> BatchUploadResponse:
    """
    여러 사진을 한 번에 업로드합니다.

    동기 단계(EXIF 파싱, 파일 저장, DB 생성)를 완료하고 결과를 즉시 반환합니다.
    LLM 분석은 백그라운드에서 진행되며, 완료 시 FCM silent push로 알림을 전송합니다.

    **백그라운드 분석 완료 시 FCM 데이터:**
    - 성공: `{"type": "analysis_complete", "diary_date": "YYYY-MM-DD"}`
    - 실패: `{"type": "analysis_failed", "diary_date": "YYYY-MM-DD"}`

    **test_mode=true:** mock 데이터 즉시 응답 (LLM 호출 없음)
    """
    if test_mode:
        return _get_mock_batch_upload_response(len(photos))

    target_date = _parse_date(date)
    _validate_photos(photos)

    file_buffers = await _read_files_to_memory(photos)

    sync_results = await batch_upload_photos_sync(
        db, user_id, target_date, file_buffers
    )

    if not sync_results:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="모든 파일 처리에 실패했습니다.",
        )

    background_tasks.add_task(
        analyze_and_notify,
        sync_results=sync_results,
        device_id=device_id,
        target_date=target_date,
    )

    results = [
        PhotoUploadResult(
            photo_id=r.photo_id,
            diary_id=r.diary_id,
            time_type=r.time_type,
            image_url=f"{settings.IMAGE_BASE_URL}/{r.image_url.removeprefix('storage/')}",
            analysis_status="processing",
        )
        for r in sync_results
    ]

    return BatchUploadResponse(results=results)


# ========================================
# 유틸리티 함수
# ========================================


def _parse_date(date_str: str) -> date:
    """날짜 문자열을 date 객체로 변환"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        ) from err


def _validate_photos(photos: list[UploadFile]) -> None:
    """업로드 파일 검증"""
    if not photos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No photos provided",
        )

    for photo in photos:
        if not photo.content_type or not photo.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type: {photo.content_type}. "
                "Only images are allowed.",
            )


async def _read_files_to_memory(
    photos: list[UploadFile],
) -> list[tuple[str, bytes, str]]:
    """UploadFile들을 메모리 바이트로 읽어둡니다.

    Returns:
        list of (filename, bytes, content_type)
    """
    buffers = []
    for photo in photos:
        content = await photo.read()
        buffers.append(
            (
                photo.filename or "unknown.jpg",
                content,
                photo.content_type or "image/jpeg",
            )
        )
    return buffers


# ========================================
# Mock 데이터 생성 함수
# ========================================


def _get_mock_batch_upload_response(photo_count: int) -> BatchUploadResponse:
    """test_mode용 mock 배치 업로드 응답 생성"""
    results = []

    for i in range(photo_count):
        time_types = ["breakfast", "lunch", "dinner", "snack"]
        time_type = time_types[i % len(time_types)]

        results.append(
            PhotoUploadResult(
                photo_id=100 + i,
                diary_id=20 + (i // 2),
                time_type=time_type,
                image_url=f"https://picsum.photos/seed/mock{i}/400/300",
                analysis_status="processing",
            )
        )

    return BatchUploadResponse(results=results)
