from datetime import UTC, datetime
from typing import Any

import httpx
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
