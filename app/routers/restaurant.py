"""음식점 검색 라우터"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_v2 as get_session
from app.core.dependencies import get_current_user_id
from app.schemas.restaurant import RestaurantSearchResponse
from app.usecases import restaurant as restaurant_usecase

router = APIRouter(prefix="/restaurant", tags=["Restaurant"])


@router.get("/search", response_model=RestaurantSearchResponse)
async def search_restaurant(
    diary_id: int | None = Query(None, description="다이어리 ID"),
    keyword: str | None = Query(None, description="음식점 이름"),
    page: int = Query(1, ge=1, le=45, description="페이지 번호"),
    size: int = Query(15, ge=1, le=15, description="페이지당 결과 수"),
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> RestaurantSearchResponse:
    """음식점 검색"""
    return await restaurant_usecase.search_restaurants(
        session=session,
        user_id=user_id,
        diary_id=diary_id,
        keyword=keyword,
        page=page,
        size=size,
    )
