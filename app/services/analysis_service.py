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
    result: list


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

    if existing:
        existing.result = data.result
    else:
        db.add(
            DiaryAnalysis(
                diary_id=data.diary_id,
                result=data.result,
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
                    "url": (
                        f"https://place.map.kakao.com/{r['kakao_id']}"
                        if r.get("kakao_id")
                        else None
                    ),
                    "road_address": r.get("road_address", ""),
                    "category": r.get("category", "").split(" > ")[-1],
                }
                for r in nearby
            ]
        except Exception as e:
            logger.warning(f"GPS 파싱 또는 식당 검색 실패: {e}")

    # LLM 1회 호출 → 객체 배열 직접 반환
    result = await analyze_food_images(image_paths, restaurant_candidates)

    return AnalysisData(
        diary_id=diary_id,
        result=result,
    )
