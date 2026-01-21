"""인증 라우터 모듈"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.deps.auth import get_google_auth_service
from app.schemas.auth import AuthCallbackResponse
from app.services.auth import GoogleAuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/google/login")
async def google_login(
    state: str | None = None,
    service: GoogleAuthService = Depends(get_google_auth_service),
) -> RedirectResponse:
    """Google OAuth 로그인 페이지로 리다이렉트합니다."""
    return RedirectResponse(url=service.get_auth_url(state))


@router.get("/google/callback", response_model=AuthCallbackResponse)
async def google_callback(
    code: str = Query(..., description="Google에서 받은 authorization code"),
    service: GoogleAuthService = Depends(get_google_auth_service),
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
