from pydantic import BaseModel, ConfigDict, Field


class PhotoStats(BaseModel):
    """사진 통계"""

    current_month_count: int = Field(..., description="이번 달 사진 수")
    previous_month_count: int = Field(..., description="지난 달 사진 수")
    change_rate: float = Field(..., description="증감률 (%). 양수는 증가, 음수는 감소")


class CategoryInfo(BaseModel):
    """카테고리 정보"""

    top_category: str = Field(..., description="가장 많이 먹은 카테고리")
    count: int = Field(..., description="해당 카테고리 횟수")


class CategoryStats(BaseModel):
    """카테고리 통계"""

    current_month: CategoryInfo = Field(..., description="이번 달 카테고리 정보")
    previous_month: CategoryInfo = Field(..., description="지난 달 카테고리 정보")


class TopMenu(BaseModel):
    """가장 많이 먹은 메뉴"""

    name: str = Field(..., description="메뉴명")
    count: int = Field(..., description="먹은 횟수")


class HourlyDistribution(BaseModel):
    """시간대별 작성 빈도"""

    hour: int = Field(..., ge=0, le=23, description="시간 (0-23)")
    count: int = Field(..., description="작성 횟수")


class DiaryTimeStats(BaseModel):
    """일기 작성 시간대 분포"""

    most_active_hour: int = Field(..., ge=0, le=23, description="가장 많이 작성한 시간대 (0-23)")
    distribution: list[HourlyDistribution] = Field(..., description="시간대별 작성 빈도")


class InsightsResponse(BaseModel):
    """인사이트 조회 응답"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "month": "2024-01",
                "photo_stats": {
                    "current_month_count": 45,
                    "previous_month_count": 30,
                    "change_rate": 50.0,
                },
                "category_stats": {
                    "current_month": {"top_category": "한식", "count": 12},
                    "previous_month": {"top_category": "양식", "count": 8},
                },
                "top_menu": {"name": "마라샹궈", "count": 5},
                "diary_time_stats": {
                    "most_active_hour": 21,
                    "distribution": [
                        {"hour": 9, "count": 2},
                        {"hour": 12, "count": 5},
                        {"hour": 18, "count": 8},
                        {"hour": 21, "count": 15},
                    ],
                },
                "keywords": ["혼밥러", "야식러버", "카페투어", "맛집탐방"],
            }
        }
    )

    month: str = Field(..., description="통계 대상 월 (YYYY-MM)")
    photo_stats: PhotoStats = Field(..., description="사진 통계")
    category_stats: CategoryStats = Field(..., description="카테고리 통계")
    top_menu: TopMenu = Field(..., description="가장 많이 먹은 메뉴")
    diary_time_stats: DiaryTimeStats = Field(..., description="일기 작성 시간대 분포")
    keywords: list[str] = Field(..., description="사용자와 가장 잘 어울리는 키워드들")
