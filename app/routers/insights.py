from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.schemas.insights import InsightsResponse
from app.services.insights import InsufficientDataError, generate_insights

router = APIRouter(prefix="/me", tags=["Insights"])


@router.get("/insights", response_model=InsightsResponse)
async def get_user_insights(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> InsightsResponse:
    """
    사용자 통계 데이터 조회

    이번 달과 저번 달의 다이어리 데이터를 기반으로 통계를 생성합니다.
    최소 데이터 요구사항을 충족하지 못하면 400 에러를 반환합니다.

    Returns:
        InsightsResponse: 사용자 통계 데이터

    Raises:
        HTTPException: 401 (인증 실패), 400 (데이터 부족), 500 (서버 에러)
    """
    try:
        return await generate_insights(session, user_id)
    except InsufficientDataError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="통계를 생성하기에 충분한 데이터가 없습니다",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="통계 조회 중 오류가 발생했습니다",
        ) from e
