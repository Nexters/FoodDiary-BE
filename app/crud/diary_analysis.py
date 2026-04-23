from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diary import Diary, DiaryAnalysis


async def get_diary_analysis(
    session: AsyncSession,
    user_id: UUID,
    diary_id: int,
) -> DiaryAnalysis | None:
    stmt = (
        select(DiaryAnalysis)
        .join(Diary, DiaryAnalysis.diary_id == Diary.id)
        .where(Diary.id == diary_id, Diary.user_id == user_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()
