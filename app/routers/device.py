from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.schemas.device import DeviceResponse, DeviceUpsertRequest
from app.usecases import device as device_usecase

router = APIRouter(prefix="/members/me", tags=["Device"])


@router.post("/device", response_model=DeviceResponse)
async def register_device(
    request: DeviceUpsertRequest,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> DeviceResponse:
    device = await device_usecase.register_device(
        session,
        user_id=user_id,
        device_id=request.device_id,
        device_token=request.device_token,
        app_version=request.app_version,
        os_version=request.os_version,
        is_active=request.is_active,
    )
    return DeviceResponse.model_validate(device)
