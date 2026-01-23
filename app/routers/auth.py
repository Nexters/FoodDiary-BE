"""인증 라우터 모듈"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.deps.auth import GoogleAuthServiceDep
from app.schemas.auth import AuthCallbackResponse, GoogleIdTokenRequest

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/google/login")
async def google_login(
    service: GoogleAuthServiceDep,
    state: str | None = None,
) -> RedirectResponse:
    """Google OAuth 로그인 페이지로 리다이렉트합니다."""
    return RedirectResponse(url=service.get_auth_url(state))


@router.get("/google/callback", response_model=AuthCallbackResponse)
async def google_callback(
    service: GoogleAuthServiceDep,
    code: Annotated[str, Query(description="Google에서 받은 authorization code")],
) -> AuthCallbackResponse:
    """
    Google OAuth 콜백을 처리합니다.

    Google 로그인 성공 후 리다이렉트되는 엔드포인트입니다.
    Authorization code를 사용해 사용자 정보를 조회하고 JWT 토큰을 발급합니다.
    """
    try:
        return await service.authenticate(code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Google 로그인 처리 중 오류가 발생했습니다: {e!s}",
        ) from e


@router.post("/google/verify", response_model=AuthCallbackResponse)
async def google_verify_id_token(
    request: GoogleIdTokenRequest,
    service: GoogleAuthServiceDep,
) -> AuthCallbackResponse:
    """
    안드로이드/iOS에서 받은 Google id_token을 검증합니다.

    모바일 앱에서 Google Sign-In SDK로 받은 id_token을 전송하면
    검증 후 사용자 정보와 JWT 토큰을 발급합니다.
    """
    try:
        return await service.authenticate_with_id_token(request.id_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Google 토큰 검증 중 오류가 발생했습니다: {e!s}",
        ) from e
