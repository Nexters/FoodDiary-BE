from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, LoginResponse, VerifyResponse
from app.services.auth import (
    TokenVerificationError,
    exchange_google_code_for_user_info,
    get_google_oauth_url,
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


@router.get("/verify", response_model=VerifyResponse)
async def verify_token(
    user_id: UUID = Depends(get_current_user_id),
) -> VerifyResponse:
    """
    JWT 토큰의 유효성을 검증합니다.

    - 유효한 토큰: 200 OK
    - 무효한 토큰: 401 Unauthorized (get_current_user_id에서 자동 처리)
    """
    return VerifyResponse(message="유효한 토큰입니다")


# ==============================================
# 웹 OAuth 엔드포인트 (서버 테스트용)
# ==============================================


@router.get("/google/login", include_in_schema=True)
async def google_web_login(
    state: str | None = None,
) -> RedirectResponse:
    """
    Google OAuth 웹 로그인 (서버 테스트용)

    브라우저에서 이 URL을 열면 Google 로그인 페이지로 리다이렉트됩니다.
    로그인 후 /auth/google/callback으로 돌아옵니다.

    Note: 안드로이드/iOS는 /auth/login (POST)를 사용하세요.
    """
    oauth_url = get_google_oauth_url(state)
    return RedirectResponse(url=oauth_url)


@router.get("/google/callback", response_model=LoginResponse)
async def google_web_callback(
    code: Annotated[str, Query(description="Google에서 받은 authorization code")],
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    """
    Google OAuth 콜백 처리 (서버 테스트용)

    Google 로그인 성공 후 자동으로 호출되는 엔드포인트입니다.
    모바일 /auth/login과 동일한 로직을 사용합니다.

    Process:
    1. Authorization code → 사용자 정보 조회
    2. 첫 로그인 시 사용자 생성 (모바일과 동일)
    3. JWT access token 발급 (모바일과 동일)

    Returns:
        모바일과 동일한 LoginResponse
    """
    # 1. Google code → 사용자 정보 조회
    try:
        provider_user_id, email = await exchange_google_code_for_user_info(code)
    except TokenVerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google 인증에 실패했습니다. 다시 시도해 주세요.",
        ) from e

    # 2. 로그인 처리 (모바일과 동일한 함수 사용!)
    try:
        user, is_first = await process_oauth_login(
            session,
            "google",
            provider_user_id,
            email,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그인 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        ) from e

    # 3. Access token 생성 (모바일과 동일!)
    access_token = create_access_token(
        user_id=str(user.id),
        provider="google",
    )

    return LoginResponse(
        id=user.id,
        access_token=access_token,
        is_first=is_first,
    )
