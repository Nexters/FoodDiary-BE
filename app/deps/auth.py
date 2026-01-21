"""인증 관련 의존성 모듈"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth import GoogleAuthService, decode_access_token

security = HTTPBearer(auto_error=False)


def get_google_auth_service() -> GoogleAuthService:
    """GoogleAuthService 의존성을 반환합니다."""
    return GoogleAuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """
    현재 인증된 사용자를 반환합니다.

    Args:
        credentials: HTTP Bearer 토큰

    Returns:
        디코드된 사용자 정보

    Raises:
        HTTPException: 인증 실패 시 401 에러
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload

