from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import diary as crud_diary
from app.schemas.insights import InsightsResponse
from app.services import insights as insights_service
from app.utils.timezone import KST


class InsufficientDataError(Exception):
    """통계 생성에 필요한 최소 데이터 부족"""

    pass


async def generate_insights(
    session: AsyncSession,
    user_id: UUID,
) -> InsightsResponse:
    now = datetime.now(KST)
    current_year, current_month = now.year, now.month

    current_start, current_end = insights_service.get_month_date_range(
        current_year, current_month
    )
    prev_year, prev_month = (
        (current_year - 1, 12)
        if current_month == 1
        else (current_year, current_month - 1)
    )
    prev_start, prev_end = insights_service.get_month_date_range(prev_year, prev_month)

    current_diaries = await crud_diary.get_diaries_for_insights(
        session, user_id, current_start, current_end, load_cover_photo=True
    )
    previous_diaries = await crud_diary.get_diaries_for_insights(
        session, user_id, prev_start, prev_end
    )

    if not insights_service.has_sufficient_data(current_diaries):
        raise InsufficientDataError(
            f"최소 {insights_service.MIN_DIARY_THRESHOLD}일의 기록이 필요합니다"
        )

    return InsightsResponse(
        month=f"{current_year:04d}-{current_month:02d}",
        photo_stats=insights_service.calculate_photo_stats(
            current_diaries, previous_diaries
        ),
        category_stats=insights_service.calculate_category_stats(
            current_diaries, previous_diaries
        ),
        weekly_stats=insights_service.calculate_weekly_stats(current_diaries),
        diary_time_stats=insights_service.calculate_diary_time_stats(current_diaries),
        tag_stats=insights_service.calculate_tag_stats(current_diaries),
        location_stats=insights_service.calculate_location_stats(current_diaries),
    )
