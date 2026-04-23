"""Photo 업로드 유스케이스"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.crud.diary import (
    apply_top_restaurant,
    get_or_create_diary,
    mark_diaries_done,
    mark_diaries_failed,
    save_diary_analysis,
)
from app.crud.photo import create_photo_for_diary, get_photos_by_diary_id
from app.schemas.photo import BatchUploadResponse, DiaryUploadResult
from app.services.analysis_service import analyze_diary_photos
from app.services.notification_service import send_silent_notification
from app.services.photo_service import PhotoSyncResult, to_upload_files
from app.utils.exif_parser import extract_exif_data
from app.utils.file_storage import save_user_photo
from app.utils.time_classifier import classify_time_type


@dataclass
class AnalysisData:
    """분석 결과 데이터"""

    diary_id: int
    result: list


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


async def analyze_and_notify(
    diary_ids: list[int],
    device_id: str,
    target_date: date,
    test_mode: bool = False,
) -> None:
    """BackgroundTask에서 호출되는 비동기 분석 단계.

    LLM 분석 + DiaryAnalysis 집계 + FCM 전송 수행.
    완료 후 Diary.analysis_status를 "done" 또는 "failed"로 업데이트.
    """
    if not diary_ids:
        return

    try:
        failed_ids = await _run_analysis_pipeline(diary_ids, test_mode=test_mode)
        succeeded_ids = [d for d in diary_ids if d not in set(failed_ids)]

        if succeeded_ids:
            async with AsyncSessionLocal() as db:
                await mark_diaries_done(db, succeeded_ids)
                await db.commit()

        async with AsyncSessionLocal() as db:
            await send_silent_notification(
                db=db,
                device_id=device_id,
                data={"type": "analysis_complete", "diary_date": str(target_date)},
            )
    except Exception as e:
        logger.exception("백그라운드 분석 실패: %s", e)
        async with AsyncSessionLocal() as db:
            await mark_diaries_failed(db, diary_ids)
            await db.commit()
        async with AsyncSessionLocal() as db:
            await send_silent_notification(
                db=db,
                device_id=device_id,
                data={"type": "analysis_failed", "diary_date": str(target_date)},
            )


async def _run_analysis_pipeline(
    diary_ids: list[int],
    test_mode: bool = False,
) -> list[int]:
    """LLM 그룹 병렬 분석 (또는 mock) + DiaryAnalysis 집계 수행.

    실패한 diary_ids를 반환합니다.
    """
    if test_mode:
        analysis_results = _create_mock_analysis_results(diary_ids)
        failed_ids: list[int] = []
    else:
        analysis_results, failed_ids = await _run_llm_analysis(diary_ids)

    for data in analysis_results:
        try:
            async with AsyncSessionLocal() as db:
                await save_diary_analysis(db, data.diary_id, data.result)
                top = _extract_top_restaurant(data.result)
                if top:
                    await apply_top_restaurant(db, data.diary_id, **top)
                await db.commit()
        except Exception as e:
            logger.warning(
                "DiaryAnalysis 집계 실패: diary_id=%d, error=%s", data.diary_id, e
            )
            failed_ids.append(data.diary_id)

    if failed_ids:
        async with AsyncSessionLocal() as db:
            await mark_diaries_failed(db, failed_ids)
            await db.commit()

    return failed_ids


_VALID_CATEGORIES = {"korean", "chinese", "japanese", "western", "etc", "home_cooked"}


def _extract_top_restaurant(result: list[dict]) -> dict | None:
    if not result:
        return None
    top = result[0]
    raw_cat = top.get("category")
    return {
        "restaurant_name": top.get("restaurant_name"),
        "restaurant_url": top.get("restaurant_url"),
        "road_address": top.get("road_address"),
        "category": raw_cat if raw_cat in _VALID_CATEGORIES else None,
        "note": top.get("memo") or None,
    }


async def _run_llm_analysis(
    diary_ids: list[int],
) -> tuple[list[AnalysisData], list[int]]:
    """diary_id별 LLM 병렬 분석을 수행합니다. (성공 결과, 실패 diary_ids) 반환"""
    logger.info("LLM 그룹 분석 시작: %d개 그룹", len(diary_ids))
    group_tasks = [_analyze_with_new_session(diary_id) for diary_id in diary_ids]
    raw_results = await asyncio.gather(*group_tasks, return_exceptions=True)

    analysis_results: list[AnalysisData] = []
    failed_ids: list[int] = []
    for diary_id, result in zip(diary_ids, raw_results, strict=True):
        if isinstance(result, AnalysisData):
            analysis_results.append(result)
        else:
            logger.warning("LLM 분석 실패: diary_id=%d, result=%s", diary_id, result)
            failed_ids.append(diary_id)

    logger.info(
        "LLM 그룹 분석 완료: 성공 %d개, 실패 %d개",
        len(analysis_results),
        len(failed_ids),
    )
    return analysis_results, failed_ids


async def _analyze_with_new_session(diary_id: int) -> AnalysisData:
    """diary_id별 독립 세션으로 LLM 분석을 수행합니다."""
    async with AsyncSessionLocal() as db:
        photos = await get_photos_by_diary_id(db, diary_id)
    result = await analyze_diary_photos(photos)
    if not result:
        raise ValueError(f"분석 결과 없음: diary_id={diary_id}")
    return AnalysisData(diary_id=diary_id, result=result)


def _create_mock_analysis_results(diary_ids: list[int]) -> list[AnalysisData]:
    logger.info("Mock 분석 데이터 생성: %d개 다이어리", len(diary_ids))
    results = [_create_mock_analysis_data(diary_id) for diary_id in diary_ids]
    logger.info("Mock 분석 데이터 생성 완료")
    return results


def _create_mock_analysis_data(diary_id: int) -> AnalysisData:
    categories = ["한식", "일식", "중식", "양식", "카페"]
    food_category = categories[diary_id % len(categories)]

    restaurant_data = {
        "한식": [
            {
                "name": "할머니집",
                "confidence": 0.85,
                "address": "서울시 강남구 테헤란로 123",
            },
            {
                "name": "명동교자",
                "confidence": 0.75,
                "address": "서울시 중구 명동길 29",
            },
        ],
        "일식": [
            {
                "name": "스시히로바",
                "confidence": 0.90,
                "address": "서울시 강남구 역삼동 456",
            },
            {
                "name": "돈코츠라멘",
                "confidence": 0.70,
                "address": "서울시 서초구 서초대로 789",
            },
        ],
        "중식": [
            {
                "name": "중화루",
                "confidence": 0.80,
                "address": "서울시 마포구 서교동 321",
            },
            {
                "name": "차이나팩토리",
                "confidence": 0.65,
                "address": "서울시 용산구 이태원로 111",
            },
        ],
        "양식": [
            {
                "name": "이탈리안키친",
                "confidence": 0.88,
                "address": "서울시 강남구 압구정로 222",
            },
            {
                "name": "스테이크하우스",
                "confidence": 0.72,
                "address": "서울시 서초구 반포대로 333",
            },
        ],
        "카페": [
            {
                "name": "스타벅스",
                "confidence": 0.92,
                "address": "서울시 강남구 선릉로 444",
            },
            {
                "name": "투썸플레이스",
                "confidence": 0.78,
                "address": "서울시 송파구 올림픽로 555",
            },
        ],
    }

    tags_data = {
        "한식": ["김치찌개", "된장찌개", "매운", "구수한", "국물"],
        "일식": ["스시세트", "라멘", "신선한", "회", "담백한"],
        "중식": ["짜장면", "짬뽕", "기름진", "볶음"],
        "양식": ["파스타", "스테이크", "크림", "치즈"],
        "카페": ["아메리카노", "카페라떼", "디저트", "달콤한"],
    }

    result = [
        {
            "restaurant_name": r["name"],
            "restaurant_url": r.get("url", ""),
            "road_address": r.get("address", ""),
            "tags": tags_data[food_category],
            "category": food_category,
            "memo": f"[TEST MODE] {r['name']} 분석 결과",
        }
        for r in restaurant_data[food_category]
    ]

    return AnalysisData(diary_id=diary_id, result=result)


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
