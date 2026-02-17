"""Photo 서비스 레이어"""

import asyncio
import logging
from datetime import date
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Diary, Photo
from app.models.diary import DiaryAnalysis
from app.schemas.photo import PhotoUploadResult
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


def _create_mock_analysis_data(
    photo_id: int, image_url: str, taken_location: str | None
) -> AnalysisData:
    """
    test_mode용 mock 분석 데이터 생성

    Args:
        photo_id: 사진 ID
        image_url: 이미지 URL
        taken_location: GPS 좌표 (latitude,longitude)

    Returns:
        AnalysisData: mock 분석 결과
    """
    # 다양한 카테고리 중 랜덤 선택
    categories = ["한식", "일식", "중식", "양식", "카페"]
    food_category = categories[photo_id % len(categories)]

    # 카테고리별 mock 식당 데이터
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

    # 카테고리별 mock 메뉴 데이터
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

    # 카테고리별 mock 키워드
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


async def batch_upload_photos(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
    files: list[UploadFile],
    test_mode: bool = False,
) -> list[PhotoUploadResult]:
    """
    여러 사진을 한 번에 업로드하고 분석합니다.

    처리 순서:
    1. 파일 저장 + DB 저장 (순차)
    2. LLM 분석 (병렬 - asyncio.gather) 또는 Mock 데이터 생성 (test_mode)
    3. DiaryAnalysis 집계

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        target_date: 대상 날짜
        files: 업로드할 파일 목록
        test_mode: True일 경우 LLM 분석 대신 mock 데이터 사용

    Returns:
        list[PhotoUploadResult]: 업로드 결과 목록
    """
    photo_infos: list[tuple[Photo, int, str]] = (
        []
    )  # [(photo, diary_id, time_type), ...]
    # diary_id별 성공한 사진 개수 추적
    diary_photo_counts: dict[int, int] = {}

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
            await db.flush()  # photo.id 생성을 위해 flush

            # commit 성공 후에 photo_count 증가 (트랜잭션 완료 시점)
            await db.commit()
            await db.refresh(photo)

            # commit 성공했으므로 카운트 증가
            diary_photo_counts[diary.id] = diary_photo_counts.get(diary.id, 0) + 1

            photo_infos.append((photo, diary.id, time_type))

        except Exception as e:
            logger.error(f"파일 처리 실패: {file.filename}, error={e}")
            # 트랜잭션 rollback 후 계속 진행
            await db.rollback()
            continue

    # ========================================
    # 1-2단계: 다이어리별 photo_count 업데이트 (실제 성공 개수 반영)
    # ========================================
    for diary_id, count in diary_photo_counts.items():
        try:
            diary_stmt = select(Diary).where(Diary.id == diary_id)
            diary_result = await db.execute(diary_stmt)
            diary = diary_result.scalar_one_or_none()
            if diary:
                diary.photo_count = (diary.photo_count or 0) + count
                await db.commit()
        except Exception as e:
            logger.warning(f"photo_count 업데이트 실패: diary_id={diary_id}, {e}")
            await db.rollback()

    if not photo_infos:
        return []

    # ========================================
    # 2단계: LLM 분석 (병렬 처리) 또는 Mock 데이터 생성
    # ========================================
    if test_mode:
        logger.info(f"Mock 분석 데이터 생성: {len(photo_infos)}개 사진")
        analysis_results: list[AnalysisData | None | BaseException] = [
            _create_mock_analysis_data(photo.id, photo.image_url, photo.taken_location)
            for photo, _, _ in photo_infos
        ]
        logger.info("Mock 분석 데이터 생성 완료")
    else:
        logger.info(f"LLM 분석 시작: {len(photo_infos)}개 사진")
        analysis_results: list[AnalysisData | None | BaseException] = (
            await asyncio.gather(
                *[
                    analyze_photo_data(photo.image_url, photo.id, photo.taken_location)
                    for photo, _, _ in photo_infos
                ],
                return_exceptions=True,
            )
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
    # 3-2단계: Diary 자동 확정 (확률 높은 후보로 채우기)
    # ========================================
    for diary_id in diary_ids:
        try:
            # DiaryAnalysis에서 후보 데이터 조회
            analysis_stmt = select(DiaryAnalysis).where(
                DiaryAnalysis.diary_id == diary_id
            )
            analysis_result = await db.execute(analysis_stmt)
            diary_analysis = analysis_result.scalar_one_or_none()

            if diary_analysis:
                # 첫 번째 후보(가장 확률 높은 것)를 Diary에 설정
                restaurant_name = None
                restaurant_url = None
                road_address = None
                category = None
                tags = []

                # restaurant_candidates에서 첫 번째 선택
                if (
                    diary_analysis.restaurant_candidates
                    and len(diary_analysis.restaurant_candidates) > 0
                ):
                    first_restaurant = diary_analysis.restaurant_candidates[0]
                    restaurant_name = first_restaurant.get("name")
                    restaurant_url = first_restaurant.get("url")
                    road_address = first_restaurant.get("address")

                # category_candidates에서 첫 번째 선택
                if (
                    diary_analysis.category_candidates
                    and len(diary_analysis.category_candidates) > 0
                ):
                    category = diary_analysis.category_candidates[0]

                # menu_candidates를 태그로 사용 (최대 5개)
                if (
                    diary_analysis.menu_candidates
                    and len(diary_analysis.menu_candidates) > 0
                ):
                    tags = diary_analysis.menu_candidates[:5]

                # Diary 업데이트
                stmt = (
                    update(Diary)
                    .where(Diary.id == diary_id)
                    .values(
                        analysis_status="done",
                        restaurant_name=restaurant_name,
                        restaurant_url=restaurant_url,
                        road_address=road_address,
                        category=category,
                        tags=tags,
                    )
                )
                await db.execute(stmt)
                await db.commit()
                logger.info(f"Diary {diary_id} 자동 확정 완료")
            else:
                # DiaryAnalysis가 없으면 status만 업데이트
                stmt = (
                    update(Diary)
                    .where(Diary.id == diary_id)
                    .values(analysis_status="done")
                )
                await db.execute(stmt)
                await db.commit()
                logger.info(f"Diary {diary_id} analysis_status 업데이트 완료")

        except Exception as e:
            logger.warning(f"Diary 자동 확정 실패: diary_id={diary_id}, error={e}")

    # ========================================
    # 4단계: 결과 반환
    # ========================================
    results = []
    for photo, diary_id, time_type in photo_infos:
        results.append(
            PhotoUploadResult(
                photo_id=photo.id,
                diary_id=diary_id,
                time_type=time_type,
                image_url=photo.image_url,
                analysis_status="done",
            )
        )

    return results
