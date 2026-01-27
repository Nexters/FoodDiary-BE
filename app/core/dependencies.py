import uuid
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.security import decode_access_token


def get_current_user_id(authorization: Annotated[str, Header()]) -> uuid.UUID:
    """
    Authorization header에서 JWT 검증 후 user_id 반환

    FastAPI dependency로 사용:
        user_id: UUID = Depends(get_current_user_id)

    Args:
        authorization: Authorization header (Bearer <token> 형식)

    Returns:
        검증된 사용자 UUID

    Raises:
        HTTPException: 401 Unauthorized (인증 실패 시)
    """
    # 1. Bearer token 추출
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="올바르지 않은 인증 형식입니다",
        )

    token = parts[1]

    # 2. JWT 검증
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
        )

    # 3. user_id 추출 및 UUID 변환
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 형식이 올바르지 않습니다",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 형식이 올바르지 않습니다",
        ) from None

    return user_id
