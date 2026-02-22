from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ======================
# Enum & Base Models
# ======================

TimeType = Literal["breakfast", "lunch", "dinner", "snack"]
AnalysisStatus = Literal["pending", "processing", "done", "failed"]


class DiaryBase(BaseModel):
    """Diary 기본 스키마"""

    diary_date: date = Field(..., description="일기 날짜")
    time_type: TimeType = Field(..., description="끼니 종류")
    restaurant_name: str | None = Field(None, description="식당명")
    restaurant_url: str | None = Field(None, description="식당 URL (예: 카카오맵 링크)")
    road_address: str | None = Field(None, description="도로명 주소")
    category: str | None = Field(None, description="음식 카테고리")
    note: str | None = Field(None, description="메모")
    tags: list[str] = Field(default=[], description="태그 리스트 (keywords + menus)")
    photo_count: int = Field(
        default=0, description="포함된 사진 수 (최대 10개)", ge=0, le=10
    )


# ======================
# Request Schemas
# ======================


class DiaryCreate(BaseModel):
    """Diary 생성 스키마 (내부 사용)"""

    user_id: UUID
    diary_date: date
    time_type: TimeType


class DiaryUpdate(BaseModel):
    """다이어리 수정 요청 스키마 (PATCH /diaries/{diary_id})"""

    category: str | None = None
    restaurant_name: str | None = None
    restaurant_url: str | None = None
    road_address: str | None = None
    note: str | None = None
    cover_photo_id: int | None = None
    photo_ids: list[int] | None = None
    tags: list[str] | None = None


class DiaryConfirm(BaseModel):
    """
    Diary 확정 스키마

    POST /diaries/{diary_id}/confirm
    유저가 AI 추정 결과를 확정할 때 사용
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "restaurant_name": "명동교자",
                "category": "한식",
                "restaurant_url": "https://place.map.kakao.com/477096726",
                "road_address": "서울 중구 명동길 29",
                "note": "칼국수가 정말 맛있었다",
                "tags": ["칼국수", "만두"],
            }
        }
    )

    restaurant_name: str = Field(..., description="확정된 식당명")
    category: str = Field(..., description="확정된 음식 카테고리")
    restaurant_url: str | None = Field(None, description="식당 URL (예: 카카오맵 링크)")
    road_address: str | None = Field(None, description="도로명 주소")
    note: str | None = Field(None, description="메모")


# ======================
# Response Schemas
# ======================


class DiaryResponse(DiaryBase):
    """Diary 응답 스키마"""

    id: int = Field(..., description="다이어리 ID")
    user_id: UUID = Field(..., description="작성자 ID")
    cover_photo_id: int | None = Field(None, description="대표 사진 ID")
    cover_photo_url: str | None = Field(None, description="대표 사진 URL")
    photo_count: int = Field(..., description="포함된 사진 수 (최대 10개)", ge=0, le=10)
    created_at: datetime = Field(..., description="생성 시각")
    updated_at: datetime = Field(..., description="수정 시각")

    model_config = ConfigDict(from_attributes=True)


class PhotoInDiary(BaseModel):
    """다이어리 조회 시 포함되는 사진 정보"""

    photo_id: int = Field(..., description="사진 ID")
    image_url: str = Field(..., description="사진 URL")
    analysis_status: AnalysisStatus = Field(..., description="분석 상태")


class AddDiaryPhotosResponse(BaseModel):
    """기존 다이어리에 사진 추가 시 응답 (POST /diaries/{diary_id}/photos)"""

    photo_ids: list[int] = Field(..., description="새로 생성된 사진 ID 목록")


class DiaryWithPhotos(DiaryResponse):
    """
    사진 목록을 포함한 다이어리 응답

    GET /diaries/{date}에서 사용
    """

    analysis_status: AnalysisStatus = Field(..., description="분석 상태")
    photos: list[PhotoInDiary] = Field(default=[], description="사진 목록")


class DatePhotosEntry(BaseModel):
    """캘린더 뷰 날짜별 사진 URL 목록"""

    photos: list[str] = Field(default=[], description="해당 날짜의 사진 URL 목록")


class DiariesByDateResponse(BaseModel):
    """
    날짜별 다이어리 목록 응답

    GET /diaries/daily
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "diaries": [
                    {
                        "id": 12,
                        "user_id": "550e8400-e29b-41d4-a716-446655440000",
                        "diary_date": "2026-01-29",
                        "time_type": "lunch",
                        "restaurant_name": "명동교자",
                        "restaurant_url": "https://place.map.kakao.com/477096726",
                        "road_address": "서울 중구 명동길 29",
                        "category": "한식",
                        "cover_photo_id": 101,
                        "note": "칼국수 맛집",
                        "tags": ["칼국수", "만두"],
                        "photo_count": 1,
                        "created_at": "2026-01-29T12:00:00Z",
                        "updated_at": "2026-01-29T12:00:00Z",
                        "analysis_status": "done",
                        "photos": [
                            {
                                "photo_id": 101,
                                "image_url": "https://...",
                                "analysis_status": "done",
                            }
                        ],
                    }
                ],
            }
        }
    )

    diaries: list[DiaryWithPhotos] = Field(default=[], description="다이어리 목록")


# ======================
# Analysis Response Schemas
# ======================


class RestaurantCandidate(BaseModel):
    """식당 후보"""

    name: str = Field(..., description="식당명")
    confidence: float | None = Field(None, description="신뢰도 (0~1)", ge=0, le=1)
    address: str | None = Field(None, description="주소")
    url: str | None = Field(None, description="식당 지도 URL")
    road_address: str | None = Field(None, description="도로명 주소")
    zone_no: str | None = Field(None, description="우편번호")


class DiaryBlogTextResponse(BaseModel):
    """
    다이어리 기반 블로그 글 생성 응답

    GET /diaries/{diary_id}/blog-text
    "블로그에 공유할 텍스트 복사" 버튼 시 사용
    """

    blog_text: str = Field(..., description="생성된 블로그 포스팅 본문 텍스트")


class DiaryAnalysisResponse(BaseModel):
    """
    다이어리 분석 후보 응답

    GET /diaries/{diary_id}/analysis
    "이 식당 맞나요?" 화면에서 사용
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "restaurant_candidates": [
                    {
                        "name": "명동교자",
                        "confidence": 0.92,
                        "address": "서울시 중구 명동길 29",
                        "url": "https://place.map.kakao.com/477096726",
                        "road_address": "서울 중구 명동길 29",
                        "zone_no": "04536",
                    }
                ],
                "category_candidates": ["한식", "분식"],
                "menu_candidates": ["칼국수", "만두", "비빔국수"],
            }
        }
    )

    restaurant_candidates: list[RestaurantCandidate] = Field(
        default=[], description="식당 후보 리스트"
    )
    category_candidates: list[str] = Field(
        default=[], description="카테고리 후보 리스트"
    )
    menu_candidates: list[str] = Field(default=[], description="메뉴 후보 리스트")
