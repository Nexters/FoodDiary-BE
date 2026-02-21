from pydantic import BaseModel, Field


class RestaurantItem(BaseModel):
    """음식점 검색 결과 항목"""

    name: str = Field(..., description="음식점 이름")
    road_address: str = Field(..., description="도로명 주소")
    url: str = Field(..., description="음식점 링크")
    category: str = Field(default="", description="음식점 카테고리")


class RestaurantSearchResponse(BaseModel):
    """음식점 검색 응답"""

    restaurants: list[RestaurantItem] = Field(default=[], description="음식점 리스트")
    total_count: int = Field(..., description="총 음식점 수")
    page: int = Field(..., description="현재 페이지")
    size: int = Field(..., description="페이지 크기")
    is_end: bool = Field(..., description="마지막 페이지 여부")
