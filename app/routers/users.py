from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.schemas.user import UserResponse
from app.services.user_service import delete_user, get_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="내 정보 조회",
)
async def get_me(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await get_user(session, user_id)
    return UserResponse(name=user.name)


@router.delete(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="회원 탈퇴",
    description="현재 로그인한 사용자의 모든 데이터와 파일을 삭제합니다.",
    responses={
        200: {
            "description": "회원 탈퇴 성공",
            "content": {
                "application/json": {
                    "example": {"message": "회원 탈퇴가 완료되었습니다."}
                }
            },
        },
        500: {
            "description": "서버 오류",
            "content": {
                "application/json": {
                    "example": {"message": "서버 오류로 회원탈퇴가 실패했습니다."}
                }
            },
        },
    },
)
async def leave(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    try:
        await delete_user(session, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버 오류로 회원탈퇴가 실패했습니다.",
        ) from e
    return {"message": "회원 탈퇴가 완료되었습니다."}
