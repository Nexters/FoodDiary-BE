"""Photo 서비스 레이어"""

import asyncio
import logging
from datetime import date
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Photo
from app.models import PhotoAnalysisResult as PhotoAnalysisResultModel
from app.schemas.diary import RestaurantCandidate
from app.schemas.photo import MenuCandidate, PhotoAnalysisResult, PhotoUploadResult
from app.services.analysis_service import (
    AnalysisData,
    aggregate_photo_analysis_to_diary,
    analyze_photo_data,
    save_photo_analysis,
)
from app.services.diary_service import get_or_create_diary
from app.utils.exif_parser import extract_exif_data
from app.utils.file_storage import save_user_photo
from app.utils.time_classifier import classify_time_type

logger = logging.getLogger(__name__)


async def batch_upload_photos(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
    files: list[UploadFile],
) -> list[PhotoUploadResult]:
    """
    여러 사진을 한 번에 업로드하고 분석합니다.

    처리 순서:
    1. 파일 저장 + DB 저장 (순차)
    2. LLM 분석 (병렬 - asyncio.gather)
    3. DiaryAnalysis 집계

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        target_date: 대상 날짜
        files: 업로드할 파일 목록

    Returns:
        list[PhotoUploadResult]: 업로드 결과 목록
    """
    photo_infos: list[tuple[Photo, int, str]] = (
        []
    )  # [(photo, diary_id, time_type), ...]

    # ========================================
    # 1단계: 파일 저장 + DB 저장 (순차 처리)
    # ========================================
    for file in files:
        try:
            # 1. EXIF 파싱
            exif_data = extract_exif_data(file.file)
            await file.seek(0)  # 파일 포인터 리셋

            # 2. 시간대 분류
            time_type = classify_time_type(exif_data["taken_at"])

            # 3. Diary upsert
            diary = await get_or_create_diary(db, user_id, target_date, time_type)

            # 4. 파일 저장
            image_url = await save_user_photo(user_id, file)

            # 5. Photo 생성
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

            # Diary의 photo_count 증가
            diary.photo_count = (diary.photo_count or 0) + 1

            await db.commit()
            await db.refresh(photo)

            photo_infos.append((photo, diary.id, time_type))

        except Exception as e:
            logger.error(f"파일 처리 실패: {file.filename}, error={e}")
            # 개별 파일 실패 시 계속 진행
            continue

    if not photo_infos:
        return []

    # ========================================
    # 2단계: LLM 분석 (병렬 처리) - DB 접근 없이
    # ========================================
    logger.info(f"LLM 분석 시작: {len(photo_infos)}개 사진")
    analysis_results: list[AnalysisData | None | BaseException] = await asyncio.gather(
        *[
            analyze_photo_data(photo.image_url, photo.id, photo.taken_location)
            for photo, _, _ in photo_infos
        ],
        return_exceptions=True,
    )
    logger.info("LLM 분석 완료")

    # ========================================
    # 2-2단계: 분석 결과 DB 저장 (순차 처리)
    # ========================================
    for result in analysis_results:
        if isinstance(result, AnalysisData):
            try:
                await save_photo_analysis(db, result)
            except Exception as e:
                logger.warning(f"분석 결과 저장 실패: photo_id={result.photo_id}, {e}")

    # ========================================
    # 3단계: DiaryAnalysis 집계
    # ========================================
    # 같은 다이어리에 대해 중복 집계 방지
    diary_ids = set(diary_id for _, diary_id, _ in photo_infos)
    for diary_id in diary_ids:
        try:
            await aggregate_photo_analysis_to_diary(db, diary_id)
        except Exception as e:
            logger.warning(f"DiaryAnalysis 집계 실패: diary_id={diary_id}, error={e}")

    # ========================================
    # 4단계: 분석 결과 조회 및 결과 반환
    # ========================================
    results = []
    for photo, diary_id, time_type in photo_infos:
        # 분석 결과 조회
        analysis_query = select(PhotoAnalysisResultModel).where(
            PhotoAnalysisResultModel.photo_id == photo.id
        )
        analysis_result = await db.execute(analysis_query)
        analysis_row = analysis_result.scalar_one_or_none()

        # 분석 결과가 있으면 스키마로 변환
        analysis = None
        if analysis_row:
            # restaurant_candidates 변환
            restaurant_candidates = []
            if analysis_row.restaurant_name_candidates:
                for r in analysis_row.restaurant_name_candidates:
                    restaurant_candidates.append(
                        RestaurantCandidate(
                            name=r.get("name", ""),
                            confidence=r.get("confidence"),
                            address=r.get("address"),
                        )
                    )

            # menu_candidates 변환
            menu_candidates = []
            if analysis_row.menu_candidates:
                for m in analysis_row.menu_candidates:
                    menu_candidates.append(
                        MenuCandidate(
                            name=m.get("name", ""),
                            price=m.get("price"),
                            confidence=m.get("confidence"),
                        )
                    )

            # keywords 변환
            keywords = analysis_row.keywords or []

            analysis = PhotoAnalysisResult(
                food_category=analysis_row.food_category,
                restaurant_candidates=restaurant_candidates,
                menu_candidates=menu_candidates,
                keywords=keywords,
            )

        results.append(
            PhotoUploadResult(
                photo_id=photo.id,
                diary_id=diary_id,
                time_type=time_type,
                image_url=photo.image_url,
                analysis=analysis,
            )
        )

    return results
