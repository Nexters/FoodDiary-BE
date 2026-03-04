from typing import Any

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import JWTError, jwt

from app.core.config import settings
from app.schemas.auth import OAuthProvider


class TokenVerificationError(Exception):
    """토큰 검증 실패 시 발생하는 예외"""

    pass


async def verify_oauth_token(provider: OAuthProvider, id_token: str) -> tuple[str, str]:
    if provider == OAuthProvider.APPLE:
        claims = await verify_apple_token(id_token)
        return claims.get("sub"), claims.get("email")
    elif provider == OAuthProvider.GOOGLE:
        claims = await verify_google_token(id_token)
        return claims.get("sub"), claims.get("email")
    else:
        raise TokenVerificationError(f"지원하지 않는 provider: {provider}")


async def verify_apple_token(
    id_token: str,
    client_id: str = settings.APPLE_CLIENT_ID,
    jwk_url: str = settings.APPLE_JWK_URL,
    base_url: str = settings.APPLE_BASE_URL,
) -> dict[str, Any]:
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


async def verify_google_token(
    id_token: str,
    client_id: str | None = None,
) -> dict[str, Any]:
    try:
        unverified_claims = jwt.get_unverified_claims(id_token)
        issuer = unverified_claims.get("iss", "")

        if issuer.startswith("https://securetoken.google.com/"):
            return await _verify_firebase_token(id_token)

        return await _verify_google_id_token(id_token, client_id)

    except ValueError as e:
        raise TokenVerificationError(f"Google ID 토큰 검증 실패: {e!s}") from e
    except Exception as e:
        raise TokenVerificationError(f"Google ID 토큰 검증 중 오류: {e!s}") from e


async def _get_apple_jwk_set(jwk_url: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(jwk_url, timeout=5.0)
        response.raise_for_status()
        return response.json()


def _validate_apple_claims(claims: dict[str, Any]) -> None:
    required_claims = {"sub", "iat", "exp", "email"}
    missing_claims = required_claims - set(claims.keys())
    if missing_claims:
        raise ValueError(f"필수 클레임 누락: {missing_claims}")


async def _verify_firebase_token(id_token: str) -> dict[str, Any]:
    try:
        firebase_certs_url = (
            "https://www.googleapis.com/robot/v1/metadata/x509/"
            "securetoken@system.gserviceaccount.com"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(firebase_certs_url, timeout=5.0)
            response.raise_for_status()
            firebase_certs = response.json()

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

        _validate_firebase_claims(idinfo)

        return idinfo

    except JWTError as e:
        raise TokenVerificationError(f"Firebase ID 토큰 검증 실패: {e!s}") from e
    except httpx.HTTPError as e:
        raise TokenVerificationError(f"Firebase 공개키 조회 실패: {e!s}") from e
    except Exception as e:
        raise TokenVerificationError(f"Firebase ID 토큰 검증 실패: {e!s}") from e


def _validate_firebase_claims(claims: dict[str, Any]) -> None:
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
    allowed_client_ids = []
    if settings.GOOGLE_CLIENT_ID:
        allowed_client_ids.append(settings.GOOGLE_CLIENT_ID)
    if settings.GOOGLE_ANDROID_CLIENT_ID:
        allowed_client_ids.append(settings.GOOGLE_ANDROID_CLIENT_ID)

    if not allowed_client_ids:
        raise TokenVerificationError("Google 클라이언트 ID가 설정되지 않았습니다")

    if client_id:
        idinfo = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            audience=client_id,
        )
    else:
        idinfo = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            audience=None,
        )

        if idinfo["iss"] not in [
            "accounts.google.com",
            "https://accounts.google.com",
        ]:
            raise TokenVerificationError("잘못된 발급자입니다")

        if idinfo.get("aud") not in allowed_client_ids:
            raise TokenVerificationError(
                f"허용되지 않은 클라이언트입니다. aud: {idinfo.get('aud')}"
            )

    _validate_google_claims(idinfo)

    return idinfo


def _validate_google_claims(claims: dict[str, Any]) -> None:
    required_claims = {"sub", "email"}
    missing_claims = required_claims - set(claims.keys())
    if missing_claims:
        raise ValueError(f"필수 클레임 누락: {missing_claims}")
