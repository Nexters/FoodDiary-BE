from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(user_id: str, provider: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "provider": provider,
        "iat": int(now.timestamp()),
    }

    if settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES > 0:
        exp = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        payload["exp"] = int(exp.timestamp())

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, str] | None:
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
