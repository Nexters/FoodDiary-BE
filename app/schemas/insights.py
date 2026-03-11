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


class CategoryCounts(BaseModel):
    """카테고리별 전체 횟수 (기본값 0)"""

    korean: int = Field(default=0, description="한식")
    chinese: int = Field(default=0, description="중식")
    japanese: int = Field(default=0, description="일식")
    western: int = Field(default=0, description="양식")
    etc: int = Field(default=0, description="기타")
    home_cooked: int = Field(default=0, description="집밥")


class CategoryStats(BaseModel):
    """카테고리 통계"""

    current_month: CategoryInfo = Field(..., description="이번 달 최다 카테고리")
    previous_month: CategoryInfo = Field(..., description="지난 달 최다 카테고리")
    current_month_counts: CategoryCounts = Field(
        ..., description="이번 달 카테고리별 전체 횟수"
    )


class KeywordStat(BaseModel):
    """키워드 통계 항목"""

    keyword: str = Field(..., description="키워드")
    count: int = Field(..., description="등장한 다이어리 수")


class LocationStat(BaseModel):
    """장소(동) 통계 항목"""

    dong: str = Field(..., description="동 이름 (예: 연남동)")
    count: int = Field(..., description="해당 동에서 식사한 횟수")


class TopMenu(BaseModel):
    """가장 많이 먹은 메뉴"""

    name: str = Field(..., description="메뉴명")
    count: int = Field(..., description="먹은 횟수")


class TimeSlotDistribution(BaseModel):
    """30분 단위 시간대별 작성 빈도"""

    time: str = Field(..., description="시간대 (HH:MM 형식, 예: 09:00, 09:30)")
    count: int = Field(..., description="작성 횟수")


class DiaryTimeStats(BaseModel):
    """일기 작성 시간대 분포 (30분 단위)"""

    most_active_time: str = Field(
        ..., description="가장 많이 작성한 시간대 (HH:MM 형식)"
    )
    distribution: list[TimeSlotDistribution] = Field(
        ..., description="30분 단위 시간대별 작성 빈도 (상위 5개, 횟수 내림차순)"
    )


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
                    "current_month": {"top_category": "korean", "count": 12},
                    "previous_month": {"top_category": "western", "count": 8},
                    "current_month_counts": {
                        "korean": 12,
                        "chinese": 3,
                        "japanese": 5,
                        "western": 2,
                        "etc": 1,
                        "home_cooked": 0,
                    },
                },
                "top_menu": {"name": "마라샹궈", "count": 5},
                "diary_time_stats": {
                    "most_active_time": "21:00",
                    "distribution": [
                        {"time": "09:00", "count": 2},
                        {"time": "12:00", "count": 5},
                        {"time": "12:30", "count": 3},
                        {"time": "18:30", "count": 8},
                        {"time": "21:00", "count": 15},
                    ],
                },
                "keywords": ["혼밥러", "야식러버", "카페투어", "맛집탐방"],
                "keyword_stats": [
                    {"keyword": "칼국수", "count": 4},
                    {"keyword": "라멘", "count": 3},
                ],
                "location_stats": [
                    {"dong": "연남동", "count": 5},
                    {"dong": "역삼동", "count": 3},
                ],
            }
        }
    )

    month: str = Field(..., description="통계 대상 월 (YYYY-MM)")
    photo_stats: PhotoStats = Field(..., description="사진 통계")
    category_stats: CategoryStats = Field(..., description="카테고리 통계")
    top_menu: TopMenu = Field(..., description="가장 많이 먹은 메뉴")
    diary_time_stats: DiaryTimeStats = Field(..., description="일기 작성 시간대 분포")
    keywords: list[str] = Field(..., description="사용자와 가장 잘 어울리는 키워드들")
    keyword_stats: list[KeywordStat] = Field(
        ..., description="이번 달 상위 키워드 (최대 10개)"
    )
    location_stats: list[LocationStat] = Field(
        ..., description="이번 달 동별 식사 횟수 (최대 10개)"
    )
