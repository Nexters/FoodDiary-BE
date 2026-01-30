from app.schemas.auth import LoginRequest, LoginResponse, OAuthProvider
from app.schemas.diary import (
    AnalysisStatus,
    DiariesByDateResponse,
    DiaryAnalysisResponse,
    DiaryBase,
    DiaryConfirm,
    DiaryCreate,
    DiaryResponse,
    DiaryUpdate,
    DiaryWithPhotos,
    PhotoInDiary,
    RestaurantCandidate,
    TimeType,
)
from app.schemas.health import HealthResponse
from app.schemas.photo import (
    BatchUploadResponse,
    MenuCandidate,
    PhotoAnalysisResultResponse,
    PhotoBase,
    PhotoCreate,
    PhotoResponse,
    PhotoUploadResult,
    PhotoWithAnalysis,
)

__all__ = [
    # Health
    "HealthResponse",
    # Auth
    "LoginRequest",
    "LoginResponse",
    "OAuthProvider",
    # Diary
    "AnalysisStatus",
    "DiariesByDateResponse",
    "DiaryAnalysisResponse",
    "DiaryBase",
    "DiaryConfirm",
    "DiaryCreate",
    "DiaryResponse",
    "DiaryUpdate",
    "DiaryWithPhotos",
    "PhotoInDiary",
    "RestaurantCandidate",
    "TimeType",
    # Photo
    "BatchUploadResponse",
    "MenuCandidate",
    "PhotoAnalysisResultResponse",
    "PhotoBase",
    "PhotoCreate",
    "PhotoResponse",
    "PhotoUploadResult",
    "PhotoWithAnalysis",
]
