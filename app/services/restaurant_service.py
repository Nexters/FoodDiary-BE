"""음식점 검색 서비스"""

from app.models.diary import DiaryAnalysis
from app.schemas.restaurant import RestaurantItem, RestaurantSearchResponse
from app.services.kakao_map_service import search_restaurants_by_keyword


def parse_diary_analysis(analysis: DiaryAnalysis | None) -> list[RestaurantItem]:
    """DiaryAnalysis JSONB 결과를 RestaurantItem 목록으로 변환"""
    if not analysis:
        return []

    return [
        RestaurantItem(
            name=c["restaurant_name"],
            road_address=c.get("road_address", ""),
            url=c.get("restaurant_url", ""),
            category=c.get("category", ""),
            tags=c.get("tags", []),
            memo=c.get("memo"),
        )
        for c in (analysis.result or [])
        if c.get("restaurant_name")
        and c.get("road_address")
        and c.get("restaurant_url")
    ]


async def search_by_keyword(
    keyword: str,
    page: int,
    size: int,
) -> RestaurantSearchResponse:
    """카카오 키워드 검색"""
    result = await search_restaurants_by_keyword(keyword, page, size)

    restaurants = [
        RestaurantItem(
            name=r["name"],
            road_address=r["road_address"],
            address_name=r.get("address_name") or None,
            url=r["url"],
            category=r.get("category", ""),
        )
        for r in result["restaurants"]
        if r["name"] and r["road_address"] and r["url"]
    ]

    return RestaurantSearchResponse(
        restaurants=restaurants,
        total_count=result["total_count"],
        page=page,
        size=size,
        is_end=result["is_end"],
    )
