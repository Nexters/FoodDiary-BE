from datetime import UTC, datetime
from typing import Any

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.auth import OAuthProvider


class TokenVerificationError(Exception):
    """토큰 검증 실패 시 발생하는 예외"""

    pass


async def process_oauth_login(
    session: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
) -> tuple[User, bool]:
    """
    OAuth 로그인 처리 - 신규/기존 사용자 분기 (비동기)

    Args:
        session: Async database session
        provider: OAuth provider 이름
        provider_user_id: Provider의 사용자 고유 ID
        email: 사용자 이메일

    Returns:
        Tuple of (User, is_first_login)
    """
    user = await get_user_by_provider_id(session, provider, provider_user_id)

    if user is None:
        user = await create_user(session, provider, provider_user_id, email)
        return user, True
    else:
        user = await update_last_login(session, user)
        return user, False


async def verify_oauth_token(provider: OAuthProvider, id_token: str) -> tuple[str, str]:
    """
    OAuth token 검증 및 사용자 정보 추출 (비동기)

    Args:
        provider: OAuth provider (apple or google)
        id_token: JWT from provider

    Returns:
        Tuple of (provider_user_id, email)

    Raises:
        TokenVerificationError: 토큰 검증 실패 시
    """
    if provider == OAuthProvider.APPLE:
        claims = await verify_apple_token(id_token)
        return claims.get("sub"), claims.get("email")
    elif provider == OAuthProvider.GOOGLE:
        claims = await verify_google_token(id_token)
        return claims.get("sub"), claims.get("email")
    else:
        raise TokenVerificationError(f"지원하지 않는 provider: {provider}")


async def get_user_by_provider_id(
    session: AsyncSession,
    provider: str,
    provider_user_id: str,
) -> User | None:
    """
    Provider와 provider_user_id로 사용자 조회 (비동기)

    Args:
        session: Async database session
        provider: OAuth provider 이름
        provider_user_id: Provider의 사용자 고유 ID

    Returns:
        User 모델 또는 None
    """
    result = await session.execute(
        select(User).where(
            User.provider == provider,
            User.provider_user_id == provider_user_id,
            User.deleted_at.is_(None),
        )
    )
    return result.scalars().first()


async def create_user(
    session: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
) -> User:
    """
    신규 사용자 생성 (비동기)

    Args:
        session: Async database session
        provider: OAuth provider 이름
        provider_user_id: Provider의 사용자 고유 ID
        email: 사용자 이메일

    Returns:
        생성된 User 모델
    """
    user = User(
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
        last_login_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_last_login(session: AsyncSession, user: User) -> User:
    """
    마지막 로그인 시각 업데이트 (비동기)

    Args:
        session: Async database session
        user: User 모델

    Returns:
        업데이트된 User 모델
    """
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    return user


async def verify_apple_token(
    id_token: str,
    client_id: str = settings.APPLE_CLIENT_ID,
    jwk_url: str = settings.APPLE_JWK_URL,
    base_url: str = settings.APPLE_BASE_URL,
) -> dict[str, Any]:
    """
    Apple ID 토큰을 JWK로 검증하고 클레임을 반환합니다.

    검증 과정:
    1. Apple JWK 공개키 세트 fetch (비동기)
    2. JWT 서명 검증 (RSA)
    3. 클레임 검증 (issuer, audience, expiration 등)

    Args:
        id_token: Apple에서 받은 ID 토큰
        client_id: Apple client ID
        jwk_url: Apple JWK URL
        base_url: Apple issuer URL

    Returns:
        검증된 JWT 클레임셋

    Raises:
        TokenVerificationError: 토큰 검증 실패 시
    """
    try:
        jwk_set = await _get_apple_jwk_set(jwk_url)

        claims = jwt.decode(
            id_token,
            jwk_set,
            algorithms=["RS256"],
            audience=client_id,
            issuer=base_url,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
            },
        )

        _validate_apple_claims(claims)

        return claims

    except (JWTError, ValueError, httpx.HTTPError) as e:
        raise TokenVerificationError(f"Apple ID 토큰 검증 실패: {e!s}") from e


async def _get_apple_jwk_set(jwk_url: str) -> dict[str, Any]:
    """
    Apple의 JWK 공개키 세트를 가져옵니다 (비동기).

    Args:
        jwk_url: Apple JWK URL

    Returns:
        JWK 공개키 세트 (keys 필드 포함)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(jwk_url, timeout=5.0)
        response.raise_for_status()
        return response.json()


def _validate_apple_claims(claims: dict[str, Any]) -> None:
    """
    필수 클레임 존재 여부를 검증합니다.

    Args:
        claims: 검증할 클레임

    Raises:
        ValueError: 필수 클레임 누락 시
    """
    required_claims = {"sub", "iat", "exp", "email"}
    missing_claims = required_claims - set(claims.keys())
    if missing_claims:
        raise ValueError(f"필수 클레임 누락: {missing_claims}")


async def verify_google_token(
    id_token: str,
    client_id: str | None = None,
) -> dict[str, Any]:
    """
    Google ID 토큰 또는 Firebase ID 토큰을 검증하고 클레임을 반환합니다.

    Firebase를 통한 Google 로그인 시 Firebase ID Token이 발급되며,
    이 경우 issuer가 'https://securetoken.google.com/{project_id}' 형식입니다.

    검증 과정:
    1. 토큰 디코딩하여 issuer 확인
    2. Firebase ID Token이면 Firebase Admin SDK로 검증
    3. Google ID Token이면 Google 공개키로 검증

    Args:
        id_token: Google 또는 Firebase에서 받은 ID 토큰
        client_id: 검증할 클라이언트 ID (None이면 모든 허용된 클라이언트 검증)

    Returns:
        검증된 JWT 클레임셋

    Raises:
        TokenVerificationError: 토큰 검증 실패 시
    """
    try:
        # 토큰을 디코딩하여 issuer 확인 (검증 없이)
        unverified_claims = jwt.get_unverified_claims(id_token)
        issuer = unverified_claims.get("iss", "")

        # Firebase ID Token인 경우
        if issuer.startswith("https://securetoken.google.com/"):
            return await _verify_firebase_token(id_token)

        # Google ID Token인 경우
        return await _verify_google_id_token(id_token, client_id)

    except ValueError as e:
        raise TokenVerificationError(f"Google ID 토큰 검증 실패: {e!s}") from e
    except Exception as e:
        raise TokenVerificationError(f"Google ID 토큰 검증 중 오류: {e!s}") from e


async def _verify_firebase_token(id_token: str) -> dict[str, Any]:
    """
    Firebase ID Token을 공개키로 검증하고 클레임을 반환합니다.

    Firebase ID Token은 Google의 공개키로 서명되지만,
    Google OAuth2와는 다른 키 세트를 사용합니다.

    Args:
        id_token: Firebase에서 받은 ID 토큰

    Returns:
        검증된 JWT 클레임셋

    Raises:
        TokenVerificationError: 토큰 검증 실패 시
    """
    try:
        # Firebase 공개키 URL
        firebase_certs_url = (
            "https://www.googleapis.com/robot/v1/metadata/x509/"
            "securetoken@system.gserviceaccount.com"
        )

        # Firebase 공개키 가져오기
        async with httpx.AsyncClient() as client:
            response = await client.get(firebase_certs_url, timeout=5.0)
            response.raise_for_status()
            firebase_certs = response.json()

        # JWT 검증
        expected_issuer = (
            f"https://securetoken.google.com/{settings.FIREBASE_PROJECT_ID}"
        )

        idinfo = jwt.decode(
            id_token,
            firebase_certs,
            algorithms=["RS256"],
            audience=settings.FIREBASE_PROJECT_ID,
            issuer=expected_issuer,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
            },
        )

        # 필수 클레임 검증
        _validate_firebase_claims(idinfo)

        return idinfo

    except JWTError as e:
        raise TokenVerificationError(f"Firebase ID 토큰 검증 실패: {e!s}") from e
    except httpx.HTTPError as e:
        raise TokenVerificationError(f"Firebase 공개키 조회 실패: {e!s}") from e
    except Exception as e:
        raise TokenVerificationError(f"Firebase ID 토큰 검증 실패: {e!s}") from e


def _validate_firebase_claims(claims: dict[str, Any]) -> None:
    """
    Firebase 필수 클레임 존재 여부를 검증합니다.

    Args:
        claims: 검증할 클레임

    Raises:
        ValueError: 필수 클레임 누락 시
    """
    # Firebase ID Token에서는 'sub' 또는 'user_id'가 사용자 ID
    # 'email'은 필수
    user_id = claims.get("sub") or claims.get("user_id")
    email = claims.get("email")

    if not user_id:
        raise ValueError("필수 클레임 누락: sub 또는 user_id")
    if not email:
        raise ValueError("필수 클레임 누락: email")


async def _verify_google_id_token(
    id_token: str,
    client_id: str | None = None,
) -> dict[str, Any]:
    """
    Google ID 토큰을 검증하고 클레임을 반환합니다.

    검증 과정:
    1. Google의 공개키로 JWT 서명 검증
    2. 클레임 검증 (issuer, audience, expiration 등)

    Args:
        id_token: Google에서 받은 ID 토큰
        client_id: 검증할 클라이언트 ID (None이면 모든 허용된 클라이언트 검증)

    Returns:
        검증된 JWT 클레임셋

    Raises:
        TokenVerificationError: 토큰 검증 실패 시
    """
    # 허용된 클라이언트 ID 목록 생성
    allowed_client_ids = []
    if settings.GOOGLE_CLIENT_ID:
        allowed_client_ids.append(settings.GOOGLE_CLIENT_ID)
    if settings.GOOGLE_ANDROID_CLIENT_ID:
        allowed_client_ids.append(settings.GOOGLE_ANDROID_CLIENT_ID)

    if not allowed_client_ids:
        raise TokenVerificationError("Google 클라이언트 ID가 설정되지 않았습니다")

    # 특정 client_id가 지정된 경우 해당 ID로만 검증
    if client_id:
        idinfo = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            audience=client_id,
        )
    else:
        # audience=None으로 검증 후 수동으로 확인
        idinfo = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            audience=None,
        )

        # 발급자 확인
        if idinfo["iss"] not in [
            "accounts.google.com",
            "https://accounts.google.com",
        ]:
            raise TokenVerificationError("잘못된 발급자입니다")

        # audience 수동 검증
        if idinfo.get("aud") not in allowed_client_ids:
            raise TokenVerificationError(
                f"허용되지 않은 클라이언트입니다. aud: {idinfo.get('aud')}"
            )

    # 필수 클레임 검증
    _validate_google_claims(idinfo)

    return idinfo


def _validate_google_claims(claims: dict[str, Any]) -> None:
    """
    Google 필수 클레임 존재 여부를 검증합니다.

    Args:
        claims: 검증할 클레임

    Raises:
        ValueError: 필수 클레임 누락 시
    """
    required_claims = {"sub", "email"}
    missing_claims = required_claims - set(claims.keys())
    if missing_claims:
        raise ValueError(f"필수 클레임 누락: {missing_claims}")


# ==============================================
# 웹 OAuth 헬퍼 함수들 (서버 테스트용)
# ==============================================


def get_google_oauth_url(state: str | None = None) -> str:
    """
    Google OAuth 인증 URL 생성 (웹 테스트용)

    Args:
        state: CSRF 방지용 state 파라미터

    Returns:
        Google 로그인 페이지 URL
    """
    from urllib.parse import urlencode

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

    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def exchange_google_code_for_user_info(code: str) -> tuple[str, str]:
    """
    Google Authorization Code를 사용자 정보로 교환 (웹 테스트용)

    Process:
    1. code → access_token 교환
    2. access_token → userinfo 조회
    3. (sub, email) 반환 → 기존 process_oauth_login() 재사용!

    Args:
        code: Google에서 받은 authorization code

    Returns:
        Tuple of (provider_user_id, email)

    Raises:
        TokenVerificationError: 토큰 교환 또는 사용자 정보 조회 실패 시
    """
    try:
        # 1. Authorization code → access token 교환
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                },
            )
            token_response.raise_for_status()
            tokens = token_response.json()

        access_token = tokens.get("access_token")
        if not access_token:
            raise TokenVerificationError("토큰 교환에 실패했습니다")

        # 2. Access token → 사용자 정보 조회
        async with httpx.AsyncClient() as client:
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()

        # 3. 필수 정보 추출 (기존 로직과 동일한 형식으로 반환)
        provider_user_id = userinfo.get("id")
        email = userinfo.get("email")

        if not provider_user_id or not email:
            raise TokenVerificationError("필수 사용자 정보 누락")

        return provider_user_id, email

    except httpx.HTTPError as e:
        raise TokenVerificationError(f"Google API 호출 실패: {e!s}") from e
    except Exception as e:
        raise TokenVerificationError(f"사용자 정보 조회 중 오류: {e!s}") from e
