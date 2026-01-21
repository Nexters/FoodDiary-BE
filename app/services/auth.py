"""인증 서비스 모듈"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from jose import jwt

from app.core.config import settings
from app.schemas.auth import (
    AuthCallbackResponse,
    GoogleUserInfo,
    TokenResponse,
    UserResponse,
)

# Google OAuth 엔드포인트
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleAuthService:
    """Google OAuth 인증 서비스"""

    def get_auth_url(self, state: str | None = None) -> str:
        """
        Google OAuth 인증 URL을 생성합니다.

        Args:
            state: CSRF 방지를 위한 state 파라미터

        Returns:
            Google 로그인 페이지 URL
        """
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state

        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def authenticate(self, code: str) -> AuthCallbackResponse:
        """
        Authorization code로 인증을 완료하고 JWT 토큰을 발급합니다.

        Args:
            code: Google에서 받은 authorization code

        Returns:
            사용자 정보와 JWT 토큰

        Raises:
            httpx.HTTPStatusError: Google API 호출 실패 시
            ValueError: 토큰 교환 실패 시
        """
        # 1. Authorization code로 토큰 교환
        tokens = await self._exchange_code_for_tokens(code)
        google_access_token = tokens.get("access_token")
        if not google_access_token:
            raise ValueError("토큰 교환에 실패했습니다.")

        # 2. Google 사용자 정보 조회
        user_info = await self._get_user_info(google_access_token)

        # 3. JWT 토큰 생성
        jwt_token = create_access_token(
            data={
                "sub": user_info.id,
                "email": user_info.email,
                "name": user_info.name,
            }
        )

        return AuthCallbackResponse(
            user=UserResponse(
                id=user_info.id,
                email=user_info.email,
                name=user_info.name,
                picture=user_info.picture,
            ),
            token=TokenResponse(access_token=jwt_token),
        )

    async def _exchange_code_for_tokens(self, code: str) -> dict:
        """Authorization code를 access token으로 교환합니다."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                },
            )
            response.raise_for_status()
            return response.json()

    async def _get_user_info(self, access_token: str) -> GoogleUserInfo:
        """Google access token으로 사용자 정보를 조회합니다."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return GoogleUserInfo(**response.json())


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    JWT access token을 생성합니다.

    Args:
        data: 토큰에 담을 데이터
        expires_delta: 만료 시간

    Returns:
        JWT 토큰 문자열
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict | None:
    """
    JWT access token을 디코드합니다.

    Args:
        token: JWT 토큰 문자열

    Returns:
        디코드된 payload 또는 유효하지 않으면 None
    """
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.JWTError:
        return None
