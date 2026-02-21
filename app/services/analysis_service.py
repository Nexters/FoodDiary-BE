"""분석 서비스 레이어"""

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DiaryAnalysis
from app.models.photo import Photo
from app.services.kakao_map_service import search_nearby_restaurants
from app.services.llm_service import analyze_food_images

logger = logging.getLogger(__name__)


@dataclass
class AnalysisData:
    """분석 결과 데이터 (DB 저장 전)"""

    diary_id: int
    food_category: str
    restaurant_candidates: list
    menu_candidates: list
    keywords: list
    raw_response: str


async def analyze_grouped_photo_data(
    db: AsyncSession,
    diary_id: int,
) -> AnalysisData | None:
    """
    같은 시간대 사진들을 한 번의 LLM 호출로 분석합니다.

    Args:
        db: 데이터베이스 세션
        diary_id: 다이어리 ID

    Returns:
        AnalysisData 또는 None (실패/타임아웃 시)
    """
    try:
        return await asyncio.wait_for(
            _analyze_grouped_photo_data_internal(db, diary_id),
            timeout=30,
        )
    except TimeoutError:
        logger.warning(f"그룹 사진 분석 타임아웃: diary_id={diary_id}")
        return None
    except Exception as e:
        logger.warning(f"그룹 사진 분석 실패: diary_id={diary_id}, error={e}")
        return None


async def aggregate_photo_analysis_to_diary(
    db: AsyncSession, data: AnalysisData
) -> None:
    """
    분석 결과를 DiaryAnalysis 테이블에 저장합니다 (upsert).

    Args:
        db: 데이터베이스 세션
        data: 분석 결과
    """
    existing = await db.get(DiaryAnalysis, data.diary_id)
    category_candidates = [data.food_category] if data.food_category else []
    menu_candidates = [mc["name"] for mc in data.menu_candidates if mc.get("name")]

    if existing:
        existing.restaurant_candidates = data.restaurant_candidates
        existing.category_candidates = category_candidates
        existing.menu_candidates = menu_candidates
        existing.keywords = data.keywords
    else:
        db.add(
            DiaryAnalysis(
                diary_id=data.diary_id,
                restaurant_candidates=data.restaurant_candidates,
                category_candidates=category_candidates,
                menu_candidates=menu_candidates,
                keywords=data.keywords,
            )
        )

    await db.commit()


async def _analyze_grouped_photo_data_internal(
    db: AsyncSession,
    diary_id: int,
) -> AnalysisData:
    """그룹 사진 분석 내부 로직."""
    rows = await db.execute(select(Photo).where(Photo.diary_id == diary_id))
    photos = rows.scalars().all()

    image_paths = [p.image_url for p in photos]
    taken_location = next((p.taken_location for p in photos if p.taken_location), None)

    # GPS가 있으면 Kakao Map 검색
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
                    "url": (
                        f"https://place.map.kakao.com/{r['kakao_id']}"
                        if r.get("kakao_id")
                        else None
                    ),
                    "road_address": r.get("road_address", ""),
                }
                for r in nearby
            ]
        except Exception as e:
            logger.warning(f"GPS 파싱 또는 식당 검색 실패: {e}")

    # 식당 후보 포함하여 LLM 1회 호출
    llm_result = await analyze_food_images(image_paths, restaurant_candidates)

    # Gemini가 선택한 순위대로 restaurant_candidates 재정렬 (최대 5개)
    ranked_names: list[str] = llm_result.get("restaurant_names", [])
    candidates_by_name = {r["name"]: r for r in restaurant_candidates}
    ranked = [candidates_by_name[n] for n in ranked_names if n in candidates_by_name]
    others = [r for r in restaurant_candidates if r["name"] not in set(ranked_names)]
    restaurant_candidates = (ranked + others)[:5]

    return AnalysisData(
        diary_id=diary_id,
        food_category=llm_result.get("food_category", "기타"),
        restaurant_candidates=restaurant_candidates,
        menu_candidates=[{"name": m} for m in llm_result.get("menus", [])],
        keywords=llm_result.get("keywords", []),
        raw_response=str(llm_result),
    )
