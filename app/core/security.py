from datetime import datetime, timedelta

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(user_id: str, provider: str) -> str:
    """
    JWT access token 생성

    Args:
        user_id: 사용자 UUID (문자열)
        provider: OAuth provider 이름

    Returns:
        인코딩된 JWT 토큰
    """
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "provider": provider,
        "iat": int(now.timestamp()),
    }

    # 만료시간 설정 (0이면 무제한)
    if settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES > 0:
        exp = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        payload["exp"] = int(exp.timestamp())

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, str] | None:
    """
    JWT access token 검증 및 디코딩 (향후 인증 미들웨어용)

    Args:
        token: JWT 토큰 문자열

    Returns:
        디코딩된 payload dict 또는 None (검증 실패 시)
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES > 0},
        )
        return payload
    except JWTError:
        return None
