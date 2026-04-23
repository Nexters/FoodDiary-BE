from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import diary_analysis as crud_diary_analysis
from app.schemas.restaurant import RestaurantItem, RestaurantSearchResponse
from app.services import restaurant_service


async def get_diary_restaurants(
    session: AsyncSession,
    user_id: UUID,
    diary_id: int,
) -> list[RestaurantItem]:
    analysis = await crud_diary_analysis.get_diary_analysis(session, user_id, diary_id)
    return restaurant_service.parse_diary_analysis(analysis)


async def search_restaurants(
    session: AsyncSession,
    user_id: UUID,
    diary_id: int | None = None,
    keyword: str | None = None,
    page: int = 1,
    size: int = 15,
) -> RestaurantSearchResponse:
    if keyword:
        return await restaurant_service.search_by_keyword(keyword, page, size)

    if diary_id:
        restaurants = await get_diary_restaurants(session, user_id, diary_id)
        return RestaurantSearchResponse(
            restaurants=restaurants,
            total_count=len(restaurants),
            page=1,
            size=len(restaurants),
            is_end=True,
        )

    return RestaurantSearchResponse(
        restaurants=[], total_count=0, page=page, size=size, is_end=True
    )
