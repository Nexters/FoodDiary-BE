from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OAuthProvider(str, Enum):
    """지원하는 OAuth provider"""

    APPLE = "apple"
    GOOGLE = "google"


class LoginRequest(BaseModel):
    """OAuth 로그인 요청"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "apple",
                "id_token": (
                    "eyJhbGciOiJSUzI1NiIsImtpZCI6IjFkZWFkYmVlZiIsInR5cCI6IkpXVCJ9..."
                ),
            }
        }
    )

    provider: OAuthProvider = Field(..., description="OAuth provider (apple or google)")
    id_token: str = Field(..., min_length=1, description="OAuth provider의 ID 토큰")


class LoginResponse(BaseModel):
    """OAuth 로그인 응답"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "is_first": True,
            }
        }
    )

    id: UUID = Field(..., description="사용자 고유 ID")
    access_token: str = Field(..., description="JWT access token")
    is_first: bool = Field(..., description="첫 로그인 여부 (true = 첫 로그인)")


class VerifyResponse(BaseModel):
    """JWT 토큰 검증 응답"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "유효한 토큰입니다",
            }
        }
    )

    message: str = Field(..., description="검증 결과 메시지")
