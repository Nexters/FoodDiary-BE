from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.schemas.device import DeviceResponse, DeviceUpsertRequest
from app.services.device import upsert_device

router = APIRouter(prefix="/members/me", tags=["Device"])


@router.post("/device", response_model=DeviceResponse)
async def register_device(
    request: DeviceUpsertRequest,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> DeviceResponse:
    """
    Device 등록/업데이트 (upsert)

    device_id 기준으로 기존 레코드가 있으면 업데이트, 없으면 생성합니다.
    하나의 기기에 여러 사용자가 접근할 수 있으므로,
    기존 device_id의 소유자가 바뀌면 user_id가 업데이트됩니다.

    Returns:
        등록/업데이트된 Device 정보
    """
    device = await upsert_device(
        session,
        user_id=user_id,
        device_id=request.device_id,
        device_token=request.device_token,
        app_version=request.app_version,
        os_version=request.os_version,
    )
    return DeviceResponse.model_validate(device)
