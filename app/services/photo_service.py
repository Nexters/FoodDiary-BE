"""Photo 서비스 레이어"""

import asyncio
import io
import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Diary, Photo
from app.services.analysis_service import (
    AnalysisData,
    aggregate_photo_analysis_to_diary,
    analyze_photo_data,
    save_photo_analysis,
)
from app.services.diary_service import get_or_create_diary
from app.services.notification_service import send_silent_notification
from app.utils.exif_parser import extract_exif_data
from app.utils.file_storage import save_user_photo
from app.utils.time_classifier import classify_time_type

logger = logging.getLogger(__name__)


@dataclass
class PhotoSyncResult:
    """동기 단계에서 생성된 사진/다이어리 정보 (비동기 단계 인수용)"""

    photo_id: int
    diary_id: int
    time_type: str
    image_url: str
    taken_location: str | None


# ========================================
# 동기 단계 (HTTP 요청 핸들러에서 호출)
# ========================================


async def batch_upload_photos_sync(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
    file_buffers: list[tuple[str, bytes, str]],
) -> list[PhotoSyncResult]:
    """
    동기 단계: EXIF 파싱 + 파일 저장 + DB 저장.

    처리 순서:
    1. EXIF 파싱 → 시간대 분류
    2. Diary upsert
    3. 파일 저장 (로컬 디스크)
    4. Photo 생성 + DB 커밋

    Args:
        db: 요청 스코프 DB 세션 (FastAPI DI 주입)
        user_id: 사용자 ID
        target_date: 대상 날짜
        file_buffers: (filename, bytes, content_type) 튜플 목록

    Returns:
        list[PhotoSyncResult]: 생성된 사진/다이어리 정보
    """
    files = _to_upload_files(file_buffers)
    results: list[PhotoSyncResult] = []

    for file in files:
        try:
            result = await _process_single_photo(db, user_id, target_date, file)
            results.append(result)
        except Exception as e:
            logger.error(f"파일 처리 실패: {file.filename}, error={e}")

    return results


# ========================================
# 백그라운드 래퍼
# ========================================


async def analyze_and_notify(
    sync_results: list[PhotoSyncResult],
    device_id: str,
    target_date: date,
    test_mode: bool = False,
) -> None:
    """
    BackgroundTask에서 호출되는 비동기 분석 단계.

    동기 단계에서 생성된 Photo/Diary 정보를 받아
    LLM 분석 + DiaryAnalysis 집계 + FCM 전송 수행.
    완료 후 Diary.analysis_status를 "done" 또는 "failed"로 업데이트.
    """
    if not sync_results:
        return

    async with AsyncSessionLocal() as db:
        try:
            await _run_analysis_pipeline(db, sync_results, test_mode=test_mode)
            await _mark_diaries_done(db, sync_results)

            await send_silent_notification(
                db=db,
                device_id=device_id,
                data={
                    "type": "analysis_complete",
                    "diary_date": str(target_date),
                },
            )
        except Exception as e:
            logger.exception(f"백그라운드 분석 실패: {e}")
            await _mark_diaries_failed(db, sync_results)
            await _notify_failure(db, target_date, device_id)


# ========================================
# 비동기 단계 파이프라인 (백그라운드)
# ========================================


async def _run_analysis_pipeline(
    db: AsyncSession,
    sync_results: list[PhotoSyncResult],
    test_mode: bool = False,
) -> None:
    """LLM 병렬 분석 (또는 mock) + 결과 저장 + DiaryAnalysis 집계 수행"""
    if test_mode:
        logger.info(f"Mock 분석 데이터 생성: {len(sync_results)}개 사진")
        analysis_results: list[AnalysisData | None | BaseException] = [
            _create_mock_analysis_data(r.photo_id) for r in sync_results
        ]
        logger.info("Mock 분석 데이터 생성 완료")
    else:
        logger.info(f"LLM 분석 시작: {len(sync_results)}개 사진")
        analysis_results = await asyncio.gather(
            *[
                analyze_photo_data(r.image_url, r.photo_id, r.taken_location)
                for r in sync_results
            ],
            return_exceptions=True,
        )
        logger.info("LLM 분석 완료")

    for result in analysis_results:
        if isinstance(result, AnalysisData):
            try:
                await save_photo_analysis(db, result)
            except Exception as e:
                logger.warning(f"분석 결과 저장 실패: photo_id={result.photo_id}, {e}")

    diary_ids = {r.diary_id for r in sync_results}
    for diary_id in diary_ids:
        try:
            await aggregate_photo_analysis_to_diary(db, diary_id)
            await _apply_top_restaurant(db, diary_id)
        except Exception as e:
            logger.warning(f"DiaryAnalysis 집계 실패: diary_id={diary_id}, error={e}")


# ========================================
# 저수준 함수
# ========================================


async def _process_single_photo(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
    file: UploadFile,
) -> PhotoSyncResult:
    """단일 파일을 처리하여 Photo DB 레코드를 생성합니다."""
    exif_data = extract_exif_data(file.file)
    await file.seek(0)

    time_type = classify_time_type(exif_data["taken_at"])
    diary = await get_or_create_diary(db, user_id, target_date, time_type)
    image_url = await save_user_photo(user_id, file)

    taken_location = None
    if exif_data["latitude"] and exif_data["longitude"]:
        taken_location = f"{exif_data['latitude']},{exif_data['longitude']}"

    photo = Photo(
        diary_id=diary.id,
        image_url=image_url,
        taken_at=exif_data["taken_at"],
        taken_location=taken_location,
    )
    db.add(photo)
    diary.photo_count = (diary.photo_count or 0) + 1

    await db.commit()
    await db.refresh(photo)

    return PhotoSyncResult(
        photo_id=photo.id,
        diary_id=diary.id,
        time_type=time_type,
        image_url=image_url,
        taken_location=taken_location,
    )


async def _mark_diaries_done(
    db: AsyncSession,
    sync_results: list[PhotoSyncResult],
) -> None:
    """분석 완료 후 Diary.analysis_status를 'done'으로 업데이트"""
    diary_ids = {r.diary_id for r in sync_results}
    for diary_id in diary_ids:
        diary = await db.get(Diary, diary_id)
        if diary:
            diary.analysis_status = "done"
    await db.commit()


async def _mark_diaries_failed(
    db: AsyncSession,
    sync_results: list[PhotoSyncResult],
) -> None:
    """분석 실패 후 Diary.analysis_status를 'failed'로 업데이트"""
    diary_ids = {r.diary_id for r in sync_results}
    for diary_id in diary_ids:
        try:
            diary = await db.get(Diary, diary_id)
            if diary:
                diary.analysis_status = "failed"
            await db.commit()
        except Exception as e:
            logger.warning(f"분석 실패 상태 업데이트 실패: diary_id={diary_id}, {e}")


async def _apply_top_restaurant(db: AsyncSession, diary_id: int) -> None:
    """DiaryAnalysis에서 가장 유력한 레스토랑 정보를 Diary에 반영"""
    from app.models import DiaryAnalysis

    diary = await db.get(Diary, diary_id)
    if not diary:
        return

    analysis = await db.get(DiaryAnalysis, diary_id)
    if analysis and analysis.restaurant_candidates:
        top = max(
            analysis.restaurant_candidates,
            key=lambda r: r.get("confidence", 0),
        )
        diary.restaurant_name = top.get("name")
        diary.restaurant_url = top.get("url")
        diary.road_address = top.get("road_address")
        await db.commit()


async def _notify_failure(
    db: AsyncSession,
    target_date: date,
    device_id: str,
) -> None:
    """백그라운드 처리 실패 시 FCM 전송"""
    try:
        await send_silent_notification(
            db=db,
            device_id=device_id,
            data={
                "type": "analysis_failed",
                "diary_date": str(target_date),
            },
        )
    except Exception:
        logger.exception("실패 알림 전송 중 에러 발생")


def _to_upload_files(
    file_buffers: list[tuple[str, bytes, str]],
) -> list[UploadFile]:
    """메모리 바이트를 UploadFile 객체로 변환"""
    return [
        UploadFile(
            file=io.BytesIO(content),
            filename=filename,
            headers={"content-type": content_type},
        )
        for filename, content, content_type in file_buffers
    ]


def _create_mock_analysis_data(photo_id: int) -> AnalysisData:
    """test_mode용 mock 분석 데이터 생성"""
    categories = ["한식", "일식", "중식", "양식", "카페"]
    food_category = categories[photo_id % len(categories)]

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

    menu_data = {
        "한식": [
            {"name": "김치찌개", "price": 8000, "confidence": 0.90},
            {"name": "된장찌개", "price": 7000, "confidence": 0.85},
        ],
        "일식": [
            {"name": "스시세트", "price": 25000, "confidence": 0.88},
            {"name": "라멘", "price": 9000, "confidence": 0.82},
        ],
        "중식": [
            {"name": "짜장면", "price": 6000, "confidence": 0.92},
            {"name": "짬뽕", "price": 7000, "confidence": 0.87},
        ],
        "양식": [
            {"name": "파스타", "price": 15000, "confidence": 0.85},
            {"name": "스테이크", "price": 35000, "confidence": 0.80},
        ],
        "카페": [
            {"name": "아메리카노", "price": 4500, "confidence": 0.95},
            {"name": "카페라떼", "price": 5000, "confidence": 0.90},
        ],
    }

    keyword_data = {
        "한식": ["매운", "구수한", "국물", "밥"],
        "일식": ["신선한", "회", "면", "담백한"],
        "중식": ["기름진", "면", "매운", "볶음"],
        "양식": ["크림", "치즈", "고기", "와인"],
        "카페": ["커피", "디저트", "달콤한", "음료"],
    }

    return AnalysisData(
        photo_id=photo_id,
        food_category=food_category,
        restaurant_candidates=restaurant_data[food_category],
        menu_candidates=menu_data[food_category],
        keywords=keyword_data[food_category],
        raw_response="[TEST MODE] Mock analysis data generated for testing",
    )
