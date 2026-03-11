from pydantic import BaseModel, ConfigDict, Field

_RESTAURANT_ITEM_EXAMPLE = {
    "name": "클래식햄버거",
    "road_address": "서울 마포구 마포대로11길 21",
    "url": "https://place.map.kakao.com/1138062048",
    "category": "western",
    "tags": ["햄버거", "탄산음료", "포장 용기", "단체 주문"],
    "memo": "테이블 위에 햄버거 포장 봉투와 음료 캔이 놓여 있습니다.",
}


class RestaurantItem(BaseModel):
    """음식점 검색 결과 항목"""

    model_config = ConfigDict(json_schema_extra={"example": _RESTAURANT_ITEM_EXAMPLE})

    name: str = Field(..., description="음식점 이름")
    road_address: str = Field(..., description="도로명 주소")
    url: str = Field(..., description="음식점 링크")
    category: str = Field(default="", description="음식점 카테고리")
    tags: list[str] = Field(default=[], description="메뉴/태그")
    memo: str | None = Field(None, description="LLM 분석 메모")
    address_name: str | None = Field(
        None, description="지번 주소 (예: 서울 마포구 연남동 224-1)"
    )


class RestaurantListResponse(BaseModel):
    """음식점 후보 목록 응답 (페이지네이션 없음)"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "restaurants": [
                    _RESTAURANT_ITEM_EXAMPLE,
                    {
                        "name": "버거킹 공덕역점",
                        "road_address": "서울 마포구 마포대로 144",
                        "url": "https://place.map.kakao.com/1940556013",
                        "category": "western",
                        "tags": ["햄버거", "탄산음료", "포장 용기", "단체 주문"],
                        "memo": "패스트푸드 매장, 햄버거 및 음료 주문.",
                    },
                ]
            }
        }
    )

    restaurants: list[RestaurantItem] = Field(default=[], description="음식점 리스트")


class RestaurantSearchResponse(BaseModel):
    """음식점 검색 응답"""

    restaurants: list[RestaurantItem] = Field(default=[], description="음식점 리스트")
    total_count: int = Field(..., description="총 음식점 수")
    page: int = Field(..., description="현재 페이지")
    size: int = Field(..., description="페이지 크기")
    is_end: bool = Field(..., description="마지막 페이지 여부")
