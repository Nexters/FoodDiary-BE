from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, LoginResponse, VerifyResponse
from app.services.auth import (
    TokenVerificationError,
    process_oauth_login,
    verify_oauth_token,
)
from app.services.device import upsert_device

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
    """
    개발/테스트용 간편 로그인

    DEBUG=true 환경에서만 작동합니다.
    실제 OAuth 인증 없이 테스트 유저로 로그인합니다.

    Request:
    - email: 테스트 유저 이메일 (기본값: test@example.com)

    Returns:
    - id: 생성된 사용자 UUID
    - access_token: JWT 토큰
    - is_first: 첫 로그인 여부
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="개발 모드에서만 사용 가능합니다. DEBUG=true 설정이 필요합니다.",
        )

    # 테스트 유저 생성/조회
    provider_user_id = f"dev_{request.email}"

    try:
        user, is_first = await process_oauth_login(
            session,
            provider="dev",
            provider_user_id=provider_user_id,
            email=request.email,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"테스트 유저 생성 실패: {e}",
        ) from e

    # Device 등록/업데이트
    await upsert_device(
        session,
        user_id=user.id,
        device_id=request.device_id,
        device_token=request.device_token,
        app_version=request.app_version,
        os_version=request.os_version,
    )

    # JWT 토큰 발급
    access_token = create_access_token(
        user_id=str(user.id),
        provider="dev",
    )

    return LoginResponse(
        id=user.id,
        access_token=access_token,
        is_first=is_first,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    """
    OAuth 로그인 (Apple, Google 등)

    Process:
    1. OAuth provider의 ID token 검증
    2. 첫 로그인 시 사용자 생성, 재로그인 시 last_login 업데이트
    3. JWT access token 발급 (만료시간 없음)

    Returns:
        - id: 사용자 UUID
        - access_token: JWT 토큰
        - is_first: 첫 로그인 여부
    """
    # 1. OAuth token 검증
    try:
        provider_user_id, email = await verify_oauth_token(
            request.provider,
            request.id_token,
        )
    except TokenVerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증에 실패했습니다. 다시 시도해 주세요.",
        ) from e

    # 2. 로그인 처리 (생성 또는 업데이트)
    try:
        user, is_first = await process_oauth_login(
            session,
            request.provider.value,
            provider_user_id,
            email,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그인 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        ) from e

    # 3. Device 등록/업데이트
    await upsert_device(
        session,
        user_id=user.id,
        device_id=request.device_id,
        device_token=request.device_token,
        app_version=request.app_version,
        os_version=request.os_version,
    )

    # 4. Access token 생성
    access_token = create_access_token(
        user_id=str(user.id),
        provider=request.provider.value,
    )

    return LoginResponse(
        id=user.id,
        access_token=access_token,
        is_first=is_first,
    )


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
) -> VerifyResponse:
    """
    JWT 토큰의 유효성을 검증합니다.

    클라이언트가 보유한 access_token이 유효한지 확인하는 엔드포인트입니다.
    로그인 상태를 확인하거나 토큰 갱신 여부를 판단할 때 사용합니다.

    Process:
    1. Authorization 헤더에서 Bearer 토큰 추출
    2. JWT 서명 및 만료시간 검증
    3. 유효한 경우 성공 응답 반환

    Returns:
        - message: 검증 결과 메시지

    Raises:
        - 401 Unauthorized: 토큰이 없거나 유효하지 않은 경우
            - "Not authenticated": Authorization 헤더 누락
            - "유효하지 않은 토큰입니다": JWT 서명이 잘못됨
            - "토큰 형식이 올바르지 않습니다": JWT 페이로드가 잘못됨
    """
    return VerifyResponse(message="유효한 토큰입니다")
