from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session_v2 as get_session
from app.core.dependencies import get_current_user_id
from app.schemas.auth import LoginRequest, LoginResponse, VerifyResponse
from app.services.oauth2 import TokenVerificationError
from app.usecases import auth as auth_usecase

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ==============================================
# 개발용 테스트 로그인 (DEBUG 모드에서만 사용)
# ==============================================


class DevLoginRequest(BaseModel):
    """개발용 로그인 요청"""

    email: str = "test@example.com"
    device_id: str = "dev-device-001"
    device_token: str | None = None
    app_version: str = "0.0.0"
    os_version: str = "0.0.0"
    is_active: bool = False


@router.post(
    "/dev/login",
    response_model=LoginResponse,
    summary="[개발용] 테스트 로그인",
    description="DEBUG 모드에서만 사용 가능한 테스트 로그인 API입니다.",
)
async def dev_login(
    request: DevLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="개발 모드에서만 사용 가능합니다. DEBUG=true 설정이 필요합니다.",
        )

    try:
        user, is_first, access_token = await auth_usecase.login_dev(
            session,
            email=request.email,
            device_id=request.device_id,
            device_token=request.device_token,
            app_version=request.app_version,
            os_version=request.os_version,
            is_active=request.is_active,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"테스트 유저 생성 실패: {e}",
        ) from e

    return LoginResponse(id=user.id, access_token=access_token, is_first=is_first)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    try:
        user, is_first, access_token = await auth_usecase.login(
            session,
            provider=request.provider.value,
            id_token=request.id_token,
            device_id=request.device_id,
            device_token=request.device_token,
            app_version=request.app_version,
            os_version=request.os_version,
            is_active=request.is_active,
        )
    except TokenVerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증에 실패했습니다. 다시 시도해 주세요.",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그인 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        ) from e

    return LoginResponse(id=user.id, access_token=access_token, is_first=is_first)


@router.get(
    "/verify",
    response_model=VerifyResponse,
    responses={
        200: {
            "description": "토큰이 유효함",
            "content": {
                "application/json": {"example": {"message": "유효한 토큰입니다"}}
            },
        },
        401: {
            "description": "토큰이 유효하지 않음",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_token": {
                            "summary": "토큰 누락",
                            "value": {"detail": "Not authenticated"},
                        },
                        "invalid_token": {
                            "summary": "유효하지 않은 토큰",
                            "value": {"detail": "유효하지 않은 토큰입니다"},
                        },
                        "malformed_token": {
                            "summary": "잘못된 토큰 형식",
                            "value": {"detail": "토큰 형식이 올바르지 않습니다"},
                        },
                        "user_not_found": {
                            "summary": "존재하지 않는 사용자",
                            "value": {"detail": "존재하지 않는 사용자입니다"},
                        },
                    }
                }
            },
        },
    },
    summary="JWT 토큰 유효성 검증",
    description="클라이언트가 보유한 access_token이 유효한지 확인합니다.",
)
async def verify_token(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> VerifyResponse:
    user = await auth_usecase.verify_user(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사용자입니다",
        )
    return VerifyResponse(message="유효한 토큰입니다")
