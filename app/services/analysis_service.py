"""분석 서비스 레이어 — 외부 API 통신 (DB 접근 없음)"""

import asyncio
import logging

from app.models.photo import Photo
from app.services.kakao_map_service import search_nearby_restaurants
from app.services.llm_service import analyze_food_images

logger = logging.getLogger(__name__)


async def analyze_diary_photos(
    photos: list[Photo],
) -> list[dict]:
    """사진 목록을 받아 LLM 분석 결과를 반환합니다."""
    try:
        return await asyncio.wait_for(
            _analyze_photos_internal(photos),
            timeout=30,
        )
    except TimeoutError:
        logger.warning("사진 분석 타임아웃")
        return []
    except Exception as e:
        logger.warning("사진 분석 실패: %s", e)
        return []


async def _analyze_photos_internal(photos: list[Photo]) -> list[dict]:
    image_paths = [p.image_url for p in photos]
    taken_location = next((p.taken_location for p in photos if p.taken_location), None)

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
            logger.warning("GPS 파싱 또는 식당 검색 실패: %s", e)

    return await analyze_food_images(image_paths, restaurant_candidates)
