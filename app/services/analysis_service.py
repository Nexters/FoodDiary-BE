"""분석 서비스 레이어"""

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DiaryAnalysis, Photo, PhotoAnalysisResult
from app.services.kakao_map_service import search_nearby_restaurants
from app.services.llm_service import analyze_food_image

logger = logging.getLogger(__name__)


@dataclass
class AnalysisData:
    """분석 결과 데이터 (DB 저장 전)"""

    photo_id: int
    food_category: str
    restaurant_candidates: list
    menu_candidates: list
    keywords: list
    raw_response: str


async def analyze_photo_data(
    image_path: str, photo_id: int, taken_location: str | None
) -> AnalysisData | None:
    """
    사진을 분석합니다 (DB 저장 없이 데이터만 반환).

    LLM + Kakao API 호출 (I/O bound - 병렬 처리에 안전)

    Args:
        image_path: 이미지 파일 경로
        photo_id: 사진 ID
        taken_location: GPS 좌표 문자열

    Returns:
        AnalysisData | None: 분석 결과 또는 None
    """
    try:
        return await asyncio.wait_for(
            _analyze_photo_data_internal(image_path, photo_id, taken_location),
            timeout=30,
        )
    except TimeoutError:
        logger.warning(f"사진 분석 타임아웃: photo_id={photo_id}")
        return None
    except Exception as e:
        logger.warning(f"사진 분석 실패: photo_id={photo_id}, error={e}")
        return None


async def _analyze_photo_data_internal(
    image_path: str, photo_id: int, taken_location: str | None
) -> AnalysisData:
    """사진 분석 내부 로직 (DB 접근 없음)"""
    # 1. LLM 분석
    llm_result = await analyze_food_image(image_path)

    # 2. GPS가 있으면 Kakao Map 검색
    restaurant_candidates = []
    if taken_location:
        try:
            lat, lng = map(float, taken_location.split(","))
            nearby = await search_nearby_restaurants(lat, lng)
            restaurant_candidates = [
                {
                    "name": r["name"],
                    "confidence": 0.8,
                    "address": r["address"],
                    "url": f"https://place.map.kakao.com/{r['kakao_id']}"
                    if r.get("kakao_id")
                    else None,
                    "road_address": r.get("road_address", ""),
                }
                for r in nearby[:5]
            ]
        except (ValueError, Exception) as e:
            logger.warning(f"GPS 파싱 또는 식당 검색 실패: {e}")

    return AnalysisData(
        photo_id=photo_id,
        food_category=llm_result.get("food_category", "기타"),
        restaurant_candidates=restaurant_candidates,
        menu_candidates=[{"name": m} for m in llm_result.get("menus", [])],
        keywords=llm_result.get("keywords", []),
        raw_response=str(llm_result),
    )


async def save_photo_analysis(
    db: AsyncSession, data: AnalysisData
) -> PhotoAnalysisResult:
    """
    분석 결과를 DB에 저장합니다 (upsert).

    Args:
        db: 데이터베이스 세션
        data: 분석 결과 데이터

    Returns:
        PhotoAnalysisResult: 저장된 결과
    """
    # 기존 결과 확인
    existing_stmt = select(PhotoAnalysisResult).where(
        PhotoAnalysisResult.photo_id == data.photo_id
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()

    if existing:
        # 기존 결과 업데이트
        existing.food_category = data.food_category
        existing.restaurant_name_candidates = data.restaurant_candidates
        existing.menu_candidates = data.menu_candidates
        existing.keywords = data.keywords
        existing.raw_response = data.raw_response
        result = existing
    else:
        # 새로 생성
        result = PhotoAnalysisResult(
            photo_id=data.photo_id,
            food_category=data.food_category,
            restaurant_name_candidates=data.restaurant_candidates,
            menu_candidates=data.menu_candidates,
            keywords=data.keywords,
            raw_response=data.raw_response,
        )
        db.add(result)

    await db.commit()
    await db.refresh(result)

    return result


async def aggregate_photo_analysis_to_diary(db: AsyncSession, diary_id: int) -> None:
    """
    다이어리에 속한 모든 사진의 분석 결과를 집계하여
    DiaryAnalysis 테이블에 저장합니다.

    Args:
        db: 데이터베이스 세션
        diary_id: 다이어리 ID
    """
    # 다이어리의 모든 사진 분석 결과 조회
    stmt = select(PhotoAnalysisResult).join(Photo).where(Photo.diary_id == diary_id)
    result = await db.execute(stmt)
    photo_results = list(result.scalars().all())

    if not photo_results:
        return

    # 집계: 식당 후보 (중복 제거)
    restaurant_candidates = []
    seen_restaurants: set[str] = set()
    for pr in photo_results:
        for rc in pr.restaurant_name_candidates or []:
            name = rc.get("name", "")
            if name and name not in seen_restaurants:
                seen_restaurants.add(name)
                restaurant_candidates.append(rc)

    # 집계: 카테고리 후보 (중복 제거)
    category_candidates = list(
        set(pr.food_category for pr in photo_results if pr.food_category)
    )

    # 집계: 메뉴 후보 (중복 제거)
    menu_candidates = []
    seen_menus: set[str] = set()
    for pr in photo_results:
        for mc in pr.menu_candidates or []:
            name = mc.get("name", "")
            if name and name not in seen_menus:
                seen_menus.add(name)
                menu_candidates.append(name)

    # DiaryAnalysis upsert
    existing = await db.get(DiaryAnalysis, diary_id)
    if existing:
        existing.restaurant_candidates = restaurant_candidates
        existing.category_candidates = category_candidates
        existing.menu_candidates = menu_candidates
    else:
        diary_analysis = DiaryAnalysis(
            diary_id=diary_id,
            restaurant_candidates=restaurant_candidates,
            category_candidates=category_candidates,
            menu_candidates=menu_candidates,
        )
        db.add(diary_analysis)

    await db.commit()
