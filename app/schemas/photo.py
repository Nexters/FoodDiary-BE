from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.diary import AnalysisStatus

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


class DiaryUploadResult(BaseModel):
    """배치 업로드 응답의 다이어리 항목"""

    diary_id: int = Field(..., description="다이어리 ID")
    diary_status: AnalysisStatus = Field(
        ..., description="분석 상태 (processing/done/failed)"
    )


class BatchUploadResponse(BaseModel):
    """
    배치 업로드 즉시 응답 (비동기 처리)

    POST /photos/batch-upload
    분석 결과는 FCM silent push로 전송됩니다.
    """

    diary_date: str = Field(..., description="대상 날짜 (YYYY-MM-DD)")
    diaries: list[DiaryUploadResult] = Field(
        default=[],
        description="생성/업데이트된 다이어리 목록",
    )
