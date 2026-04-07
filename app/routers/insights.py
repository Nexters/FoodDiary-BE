import random
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.schemas.insights import (
    CategoryCounts,
    CategoryInfo,
    CategoryStats,
    DiaryTimeStats,
    InsightsResponse,
    LocationStat,
    PhotoStats,
    TagStat,
    TimeSlotDistribution,
    WeeklyStats,
    WeekStat,
)
from app.usecases.insights import InsufficientDataError, generate_insights

router = APIRouter(prefix="/me", tags=["Insights"])


@router.get("/insights", response_model=InsightsResponse)
async def get_user_insights(
    test_mode: Annotated[
        bool, Query(description="테스트 모드 (mock 데이터 반환)")
    ] = False,
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
    if test_mode:
        return _get_mock_insights()

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


def _get_mock_insights() -> InsightsResponse:
    categories = ["korean", "chinese", "japanese", "western", "etc", "home_cooked"]
    all_dongs = [
        "연남동",
        "역삼동",
        "홍대",
        "강남",
        "신촌",
        "이태원",
        "성수동",
        "망원동",
    ]
    all_tag_words = [
        "칼국수",
        "라멘",
        "파스타",
        "스시",
        "삼겹살",
        "마라탕",
        "치킨",
        "버거",
    ]

    current_count = random.randint(10, 60)
    previous_count = random.randint(10, 60)
    change_rate = round((current_count - previous_count) / previous_count * 100, 1)

    category_counts_values = [random.randint(0, 15) for _ in categories]
    top_idx = category_counts_values.index(max(category_counts_values))
    prev_top = random.choice(categories)

    sample_hours = sorted(random.sample(range(7, 24), k=random.randint(4, 7)))
    sample_slots = sorted(
        {
            f"{h:02d}:{m:02d}"
            for h in sample_hours
            for m in random.sample([0, 30], k=random.randint(1, 2))
        }
    )
    most_active_slot = random.choice(sample_slots)
    distribution = [
        TimeSlotDistribution(time=slot, count=random.randint(1, 15))
        for slot in sample_slots
    ]

    week_counts = [random.randint(0, 10) for _ in range(4)]
    most_active_week = week_counts.index(max(week_counts)) + 1

    from app.utils.timezone import KST  # mock 함수 내부에서만 사용

    now = datetime.now(KST)
    return InsightsResponse(
        month=now.strftime("%Y-%m"),
        photo_stats=PhotoStats(
            current_month_count=current_count,
            previous_month_count=previous_count,
            change_rate=change_rate,
        ),
        category_stats=CategoryStats(
            current_month=CategoryInfo(
                top_category=categories[top_idx],
                count=category_counts_values[top_idx],
            ),
            previous_month=CategoryInfo(
                top_category=prev_top, count=random.randint(3, 15)
            ),
            current_month_counts=CategoryCounts(
                korean=category_counts_values[0],
                chinese=category_counts_values[1],
                japanese=category_counts_values[2],
                western=category_counts_values[3],
                etc=category_counts_values[4],
                home_cooked=category_counts_values[5],
            ),
        ),
        weekly_stats=WeeklyStats(
            most_active_week=most_active_week,
            weekly_counts=[
                WeekStat(week=i + 1, count=week_counts[i]) for i in range(4)
            ],
        ),
        diary_time_stats=DiaryTimeStats(
            most_active_time=most_active_slot,
            distribution=distribution,
        ),
        tag_stats=[
            TagStat(keyword=tag, count=random.randint(1, 6))
            for tag in random.sample(all_tag_words, k=random.randint(3, 5))
        ],
        location_stats=[
            LocationStat(dong=dong, count=random.randint(1, 8))
            for dong in random.sample(all_dongs, k=random.randint(3, 5))
        ],
    )
