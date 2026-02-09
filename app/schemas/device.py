from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceUpsertRequest(BaseModel):
    """Device 등록/업데이트 요청"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
                "device_token": "fcm_token_abc123...",
                "app_version": "1.0.0",
                "os_version": "18.2",
            }
        }
    )

    device_id: str = Field(..., max_length=255, description="디바이스 고유 ID")
    device_token: str | None = Field(None, max_length=255, description="푸시 알림 토큰")
    app_version: str = Field(..., max_length=20, description="앱 버전")
    os_version: str = Field(..., max_length=20, description="OS 버전")


class DeviceResponse(BaseModel):
    """Device 응답"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Device PK")
    device_id: str = Field(..., description="디바이스 고유 ID")
    is_active: bool = Field(..., description="활성 여부")
    device_token: str | None = Field(None, description="푸시 알림 토큰")
    app_version: str = Field(..., description="앱 버전")
    os_version: str = Field(..., description="OS 버전")
    created_at: datetime = Field(..., description="생성 시각")
    updated_at: datetime = Field(..., description="수정 시각")
