"""음식점 검색 서비스"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diary import Diary, DiaryAnalysis
from app.schemas.restaurant import RestaurantItem, RestaurantSearchResponse
from app.services.kakao_map_service import search_restaurants_by_keyword


async def search_restaurants(
    session: AsyncSession,
    user_id: UUID,
    diary_id: int | None = None,
    keyword: str | None = None,
    page: int = 1,
    size: int = 15,
) -> RestaurantSearchResponse:
    """음식점 검색 오케스트레이션"""
    if keyword:
        return await _search_by_keyword(keyword, page, size)

    if diary_id:
        return await _search_by_diary(session, user_id, diary_id)

    return RestaurantSearchResponse(
        restaurants=[], total_count=0, page=page, size=size, is_end=True
    )


async def _search_by_keyword(
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


async def _search_by_diary(
    session: AsyncSession,
    user_id: UUID,
    diary_id: int,
) -> RestaurantSearchResponse:
    """diary_analysis에서 음식점 후보 조회"""
    stmt = (
        select(DiaryAnalysis)
        .join(Diary, DiaryAnalysis.diary_id == Diary.id)
        .where(Diary.id == diary_id, Diary.user_id == user_id)
    )
    analysis = (await session.execute(stmt)).scalar_one_or_none()

    if not analysis:
        return RestaurantSearchResponse(
            restaurants=[], total_count=0, page=1, size=15, is_end=True
        )

    restaurants = [
        RestaurantItem(
            name=c["restaurant_name"],
            road_address=c.get("road_address", ""),
            url=c.get("restaurant_url", ""),
        )
        for c in (analysis.result or [])
        if c.get("restaurant_name")
        and c.get("road_address")
        and c.get("restaurant_url")
    ]

    return RestaurantSearchResponse(
        restaurants=restaurants,
        total_count=len(restaurants),
        page=1,
        size=len(restaurants),
        is_end=True,
    )
