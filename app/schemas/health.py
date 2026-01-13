from pydantic import BaseModel


class HealthResponse(BaseModel):
    """헬스체크 응답 모델"""

    status: str

