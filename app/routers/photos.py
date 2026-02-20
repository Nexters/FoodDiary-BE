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


@router.post(
    "/batch-upload",
    response_model=BatchUploadResponse,
    responses={
        200: {
            "description": (
                "업로드 성공. 분석은 백그라운드에서 진행되며 "
                "FCM silent push로 결과를 수신합니다."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "message": "Upload received, analysis in progress",
                        "results": [
                            {
                                "photo_id": 19,
                                "diary_id": 2,
                                "time_type": "dinner",
                                "image_url": "https://mumuk.ai.kr/static/photos/uuid/uuid.jpg",
                                "analysis_status": "processing",
                            }
                        ],
                    }
                }
            },
        },
        400: {"description": "파일 없음 또는 이미지가 아닌 파일 포함"},
        422: {"description": "모든 파일 처리 실패"},
    },
)
async def batch_upload_photos_endpoint(
    date: Annotated[str, Form(description="대상 날짜 (YYYY-MM-DD, 예: 2026-02-20)")],
    device_id: Annotated[str, Form(description="FCM silent push를 수신할 디바이스 ID")],
    photos: Annotated[
        list[UploadFile],
        File(description="업로드할 이미지 파일들 (1개 이상, image/* 타입만 허용)"),
    ],
    background_tasks: BackgroundTasks,
    test_mode: Annotated[
        bool,
        Query(
            description=(
                "테스트 모드: LLM 분석을 mock 데이터로 대체하고 "
                "FCM silent push도 전송"
            )
        ),
    ] = False,
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> BatchUploadResponse:
    """
    여러 사진을 한 번에 업로드합니다.

    ## 처리 흐름

    **동기 단계 (즉시 응답)**
    1. EXIF 파싱 → 촬영 시각 기준으로 끼니(breakfast/lunch/dinner/snack) 자동 분류
    2. Diary upsert (user_id + date + time_type 조합)
    3. 파일 저장 → Photo DB 생성
    4. `analysis_status: "processing"` 상태로 즉시 응답 반환

    **백그라운드 단계 (비동기)**
    1. Gemini LLM으로 음식 사진 분석 (병렬)
    2. DiaryAnalysis 집계 (식당 후보, 카테고리, 메뉴)
    3. 가장 유력한 식당 정보를 Diary에 반영
    4. FCM silent push 전송

    ## FCM Silent Push 데이터

    - 성공: `{"type": "analysis_complete", "diary_date": "YYYY-MM-DD"}`
    - 실패: `{"type": "analysis_failed", "diary_date": "YYYY-MM-DD"}`

    FCM 수신 후 `GET /diaries?start_date=...&end_date=...` 로 최신 데이터를 조회하세요.

    ## test_mode

    `test_mode=true`로 요청하면 LLM 호출 없이 mock 분석 데이터를 사용하며,
    분석 완료 후 실제 FCM silent push도 전송됩니다.
    """
    if test_mode:
        return await _get_mock_batch_upload_response(
            len(photos), device_id, date, background_tasks
        )

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


async def _get_mock_batch_upload_response(
    photo_count: int,
    device_id: str,
    date_str: str,
    background_tasks: BackgroundTasks,
) -> BatchUploadResponse:
    """test_mode용 mock 배치 업로드 응답 생성 및 백그라운드 silent push 예약"""
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

    background_tasks.add_task(
        _send_mock_silent_push,
        device_id=device_id,
        date_str=date_str,
    )

    return BatchUploadResponse(results=results)


async def _send_mock_silent_push(device_id: str, date_str: str) -> None:
    """test_mode용 FCM silent push 전송"""
    from app.core.database import AsyncSessionLocal
    from app.services.notification_service import send_silent_notification

    async with AsyncSessionLocal() as db:
        await send_silent_notification(
            db=db,
            device_id=device_id,
            data={"type": "analysis_complete", "diary_date": date_str},
        )
