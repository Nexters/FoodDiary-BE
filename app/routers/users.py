from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.services.user_service import delete_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회원 탈퇴",
    description="현재 로그인한 사용자의 모든 데이터와 파일을 삭제합니다.",
)
async def leave(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    await delete_user(session, user_id)
