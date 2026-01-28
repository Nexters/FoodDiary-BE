from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth import (
    TokenVerificationError,
    process_oauth_login,
    verify_oauth_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


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

    # 3. Access token 생성
    access_token = create_access_token(
        user_id=str(user.id),
        provider=request.provider.value,
    )

    return LoginResponse(
        id=user.id,
        access_token=access_token,
        is_first=is_first,
    )
