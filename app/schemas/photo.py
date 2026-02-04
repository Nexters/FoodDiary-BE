from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.diary import AnalysisStatus, RestaurantCandidate, TimeType

# ======================
# Base Models
# ======================


class PhotoBase(BaseModel):
    """Photo 기본 스키마"""

    image_url: str = Field(..., description="사진 URL")
    taken_at: datetime | None = Field(None, description="촬영 시각 (EXIF)")
    taken_location: str | None = Field(
        None, description="촬영 위치 GPS 좌표 (longitude, latitude)"
    )


# ======================
# Request Schemas
# ======================


class PhotoCreate(BaseModel):
    """Photo 생성 스키마 (내부 사용)"""

    diary_id: int
    image_url: str
    taken_at: datetime | None = None
    taken_location: str | None = None


# ======================
# Analysis Result Schemas (먼저 정의)
# ======================


class MenuCandidate(BaseModel):
    """메뉴 후보"""

    name: str = Field(..., description="메뉴명")
    price: int | None = Field(None, description="가격", ge=0)
    confidence: float | None = Field(None, description="신뢰도 (0~1)", ge=0, le=1)


class PhotoAnalysisResult(BaseModel):
    """사진 분석 결과 (업로드 응답에 포함)"""

    food_category: str | None = Field(None, description="음식 카테고리")
    restaurant_candidates: list[RestaurantCandidate] = Field(
        default=[], description="식당 후보 리스트"
    )
    menu_candidates: list[MenuCandidate] = Field(
        default=[], description="메뉴 후보 리스트"
    )
    keywords: list[str] = Field(default=[], description="음식 키워드")


# ======================
# Response Schemas
# ======================


class PhotoResponse(PhotoBase):
    """Photo 응답 스키마"""

    id: int = Field(..., description="사진 ID")
    diary_id: int = Field(..., description="소속 다이어리 ID")
    created_at: datetime = Field(..., description="생성 시각")
    updated_at: datetime = Field(..., description="수정 시각")

    model_config = ConfigDict(from_attributes=True)


class PhotoUploadResult(BaseModel):
    """
    사진 업로드 결과

    POST /photos/batch-upload 응답 항목
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "photo_id": 101,
                "diary_id": 12,
                "time_type": "lunch",
                "image_url": "data/photos/abc123.jpg",
                "analysis": {
                    "food_category": "한식",
                    "restaurant_candidates": [
                        {
                            "name": "명동교자",
                            "confidence": 0.92,
                            "address": "서울시 중구",
                        }
                    ],
                    "menu_candidates": [{"name": "칼국수"}],
                    "keywords": ["얼큰한", "구수한"],
                },
            }
        }
    )

    photo_id: int = Field(..., description="생성된 사진 ID")
    diary_id: int = Field(..., description="연결된 다이어리 ID")
    time_type: TimeType = Field(..., description="분류된 끼니 종류")
    image_url: str = Field(..., description="이미지 URL")
    analysis: PhotoAnalysisResult | None = Field(
        None, description="분석 결과 (분석 완료 시)"
    )


class BatchUploadResponse(BaseModel):
    """
    배치 업로드 응답

    POST /photos/batch-upload
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "photo_id": 101,
                        "diary_id": 12,
                        "time_type": "lunch",
                        "image_url": "data/photos/abc123.jpg",
                        "analysis": {
                            "food_category": "한식",
                            "restaurant_candidates": [
                                {"name": "명동교자", "confidence": 0.92}
                            ],
                            "menu_candidates": [{"name": "칼국수"}],
                            "keywords": ["얼큰한"],
                        },
                    }
                ]
            }
        }
    )

    results: list[PhotoUploadResult] = Field(..., description="업로드 및 분석 결과")


class PhotoAnalysisResultResponse(BaseModel):
    """
    사진 분석 결과 응답

    PhotoAnalysisResult 모델의 응답 스키마
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "photo_id": 101,
                "food_category": "한식",
                "restaurant_name_candidates": [
                    {
                        "name": "명동교자",
                        "confidence": 0.92,
                        "address": "서울시 중구 명동길 29",
                    }
                ],
                "menu_candidates": [
                    {"name": "칼국수", "price": 8000, "confidence": 0.95},
                    {"name": "만두", "price": 5000, "confidence": 0.88},
                ],
                "keywords": ["얼큰한", "구수한", "손칼국수"],
            }
        },
    )

    photo_id: int = Field(..., description="사진 ID")
    food_category: str | None = Field(None, description="음식 카테고리")
    restaurant_name_candidates: list[RestaurantCandidate] = Field(
        default=[], description="식당 후보 리스트"
    )
    menu_candidates: list[MenuCandidate] = Field(
        default=[], description="메뉴 후보 리스트"
    )
    keywords: list[str] = Field(default=[], description="음식 키워드")


class PhotoWithAnalysis(PhotoResponse):
    """분석 결과를 포함한 사진 응답"""

    analysis_status: AnalysisStatus = Field(..., description="분석 상태")
    analysis_result: PhotoAnalysisResultResponse | None = Field(
        None, description="분석 결과 (완료된 경우)"
    )
