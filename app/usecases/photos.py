"""Photo 업로드 유스케이스"""

import logging
from datetime import date
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.diary import get_or_create_diary
from app.crud.photo import create_photo_for_diary
from app.schemas.photo import BatchUploadResponse, DiaryUploadResult
from app.services.diary_service import MAX_PHOTOS_PER_DIARY
from app.services.photo_service import PhotoSyncResult, to_upload_files
from app.usecases.diary import PhotoLimitExceededError, analyze_and_notify
from app.utils.exif_parser import extract_exif_data
from app.utils.file_storage import save_user_photo
from app.utils.time_classifier import classify_time_type

logger = logging.getLogger(__name__)


async def batch_upload_photos(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
    device_id: str,
    file_buffers: list[tuple[str, bytes, str]],
    background_tasks: BackgroundTasks,
) -> BatchUploadResponse:
    sync_results = await _batch_upload_photos_sync(
        db, user_id, target_date, file_buffers
    )

    if not sync_results:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="모든 파일 처리에 실패했습니다.",
        )

    diary_ids = list(dict.fromkeys(r.diary_id for r in sync_results if r.is_new_diary))
    background_tasks.add_task(
        analyze_and_notify,
        diary_ids=diary_ids,
        device_id=device_id,
        target_date=target_date,
    )

    seen: dict[int, tuple[str, str]] = {}
    for r in sync_results:
        if r.diary_id not in seen:
            seen[r.diary_id] = (r.analysis_status, r.time_type)

    diaries = [
        DiaryUploadResult(
            diary_id=did, diary_status=analysis_status, time_type=time_type
        )
        for did, (analysis_status, time_type) in seen.items()
    ]
    return BatchUploadResponse(diary_date=str(target_date), diaries=diaries)


async def _batch_upload_photos_sync(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
    file_buffers: list[tuple[str, bytes, str]],
) -> list[PhotoSyncResult]:
    files = to_upload_files(file_buffers)
    results: list[PhotoSyncResult] = []

    for file in files:
        try:
            result = await _process_single_photo(db, user_id, target_date, file)
            results.append(result)
        except Exception as e:
            logger.error("파일 처리 실패: %s, error=%s", file.filename, e)

    return results


async def _process_single_photo(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
    file: UploadFile,
) -> PhotoSyncResult:
    exif_data = extract_exif_data(file.file)
    await file.seek(0)

    time_type = classify_time_type(exif_data["taken_at"])
    diary, is_new_diary = await get_or_create_diary(db, user_id, target_date, time_type)
    if diary.photo_count >= MAX_PHOTOS_PER_DIARY:
        raise PhotoLimitExceededError(
            f"다이어리당 최대 {MAX_PHOTOS_PER_DIARY}개의 사진만 저장할 수 있습니다."
        )
    image_url = await save_user_photo(user_id, file)

    taken_location = None
    if exif_data["latitude"] and exif_data["longitude"]:
        taken_location = f"{exif_data['latitude']},{exif_data['longitude']}"

    photo = await create_photo_for_diary(
        db, diary, image_url, exif_data["taken_at"], taken_location
    )

    return PhotoSyncResult(
        photo_id=photo.id,
        diary_id=diary.id,
        time_type=time_type,
        image_url=image_url,
        is_new_diary=is_new_diary,
        analysis_status=diary.analysis_status or "processing",
    )
