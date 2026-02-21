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

    POST /photos/batch-upload 응답
    - 일반 모드: 파일 저장 및 Diary 생성만 완료 (analysis_status: "processing")
    - test_mode: 분석 결과도 포함하여 즉시 응답 (analysis_status: "done")
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "photo_id": 19,
                "diary_id": 2,
                "time_type": "dinner",
                "image_url": "data/photos/22a85dba-9ad1-4c87-9fa8-26cd5aefe096.JPG",
                "analysis_status": "processing",
            }
        }
    )

    photo_id: int = Field(..., description="생성된 사진 ID")
    diary_id: int = Field(..., description="연결된 다이어리 ID")
    time_type: TimeType = Field(..., description="분류된 끼니 종류")
    image_url: str = Field(..., description="이미지 URL")
    analysis_status: AnalysisStatus = Field(
        ..., description="분석 상태 (processing/done/failed)"
    )


class BatchUploadResponse(BaseModel):
    """
    배치 업로드 즉시 응답 (비동기 처리)

    POST /photos/batch-upload
    분석 결과는 FCM silent push로 전송됩니다.
    """

    message: str = Field(
        default="Upload received, analysis in progress",
        description="처리 상태 메시지",
    )
    results: list[PhotoUploadResult] = Field(
        default=[],
        description="업로드된 사진 목록 (analysis_status: processing)",
    )


