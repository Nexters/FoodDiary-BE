from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """서버 상태 확인 엔드포인트"""
    return HealthResponse(status="ok")

