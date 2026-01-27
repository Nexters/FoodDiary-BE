from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diary import Diary
from app.schemas.insights import (
    CategoryInfo,
    CategoryStats,
    DiaryTimeStats,
    HourlyDistribution,
    InsightsResponse,
    PhotoStats,
    TopMenu,
)

MIN_DIARY_THRESHOLD = 3


class InsufficientDataError(Exception):
    """통계 생성에 필요한 최소 데이터 부족"""

    pass


async def generate_insights(
    session: AsyncSession,
    user_id: UUID,
) -> InsightsResponse:
    """
    사용자 인사이트 생성 (메인 함수)

    Args:
        session: DB 세션
        user_id: 사용자 UUID

    Returns:
        InsightsResponse 모델

    Raises:
        InsufficientDataError: 데이터가 부족한 경우
    """
    # 현재 날짜 기준으로 이번 달/저번 달 계산 (한국 시간 KST, UTC+9)
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    current_year = now.year
    current_month = now.month

    # 이번 달 범위
    current_range = get_month_date_range(current_year, current_month)

    # 저번 달 범위
    if current_month == 1:
        previous_range = get_month_date_range(current_year - 1, 12)
    else:
        previous_range = get_month_date_range(current_year, current_month - 1)

    # 이번 달 데이터 조회
    current_result = await session.execute(
        select(Diary).where(
            Diary.user_id == user_id,
            Diary.diary_date >= current_range[0],
            Diary.diary_date < current_range[1],
            Diary.deleted_at.is_(None),
        )
    )
    current_diaries = list(current_result.scalars().all())

    # 저번 달 데이터 조회
    previous_result = await session.execute(
        select(Diary).where(
            Diary.user_id == user_id,
            Diary.diary_date >= previous_range[0],
            Diary.diary_date < previous_range[1],
            Diary.deleted_at.is_(None),
        )
    )
    previous_diaries = list(previous_result.scalars().all())

    # 최소 데이터 확인
    if len(current_diaries) < MIN_DIARY_THRESHOLD:
        raise InsufficientDataError(
            f"최소 {MIN_DIARY_THRESHOLD}개의 다이어리가 필요합니다 "
            f"(현재: {len(current_diaries)}개)"
        )

    # 메모리에서 통계 계산
    photo_stats = calculate_photo_stats(current_diaries, previous_diaries)
    category_stats = calculate_category_stats(current_diaries, previous_diaries)
    time_stats = calculate_diary_time_stats(current_diaries)
    top_menu = calculate_top_menu(current_diaries)
    keywords = calculate_keywords(current_diaries)

    # 응답 조합
    return InsightsResponse(
        month=f"{current_year:04d}-{current_month:02d}",
        photo_stats=photo_stats,
        category_stats=category_stats,
        top_menu=top_menu,
        diary_time_stats=time_stats,
        keywords=keywords,
    )


def calculate_photo_stats(
    current_diaries: list[Diary],
    previous_diaries: list[Diary],
) -> PhotoStats:
    """
    사진 통계 계산 (이번 달 vs 저번 달)

    Args:
        current_diaries: 이번 달 다이어리 목록
        previous_diaries: 저번 달 다이어리 목록

    Returns:
        PhotoStats 모델
    """
    current_count = sum(d.photo_count for d in current_diaries)
    previous_count = sum(d.photo_count for d in previous_diaries)

    # 증감률 계산
    if previous_count > 0:
        change_rate = ((current_count - previous_count) / previous_count) * 100
    elif current_count > 0:
        change_rate = 100.0  # 0에서 증가한 경우 100%
    else:
        change_rate = 0.0  # 둘 다 0인 경우

    return PhotoStats(
        current_month_count=current_count,
        previous_month_count=previous_count,
        change_rate=round(change_rate, 1),
    )


def calculate_category_stats(
    current_diaries: list[Diary],
    previous_diaries: list[Diary],
) -> CategoryStats:
    """
    카테고리 통계 계산 (가장 많이 먹은 카테고리)

    Args:
        current_diaries: 이번 달 다이어리 목록
        previous_diaries: 저번 달 다이어리 목록

    Returns:
        CategoryStats 모델
    """
    # 이번 달 카테고리 카운트
    current_counter = Counter(d.category for d in current_diaries)
    if current_counter:
        top_category, count = current_counter.most_common(1)[0]
        current_info = CategoryInfo(top_category=top_category, count=count)
    else:
        current_info = CategoryInfo(top_category="데이터 없음", count=0)

    # 저번 달 카테고리 카운트
    previous_counter = Counter(d.category for d in previous_diaries)
    if previous_counter:
        top_category, count = previous_counter.most_common(1)[0]
        previous_info = CategoryInfo(top_category=top_category, count=count)
    else:
        previous_info = CategoryInfo(top_category="데이터 없음", count=0)

    return CategoryStats(
        current_month=current_info,
        previous_month=previous_info,
    )


def calculate_diary_time_stats(current_diaries: list[Diary]) -> DiaryTimeStats:
    """
    일기 작성 시간대 통계 계산

    Args:
        current_diaries: 이번 달 다이어리 목록

    Returns:
        DiaryTimeStats 모델
    """
    if not current_diaries:
        return DiaryTimeStats(
            most_active_hour=12,
            distribution=[],
        )

    # 시간대별 카운트
    hour_counter = Counter(d.diary_date.hour for d in current_diaries)

    # 가장 활발한 시간대
    most_active_hour = hour_counter.most_common(1)[0][0]

    # 분포 배열 생성 (시간순 정렬)
    distribution = [
        HourlyDistribution(hour=hour, count=count)
        for hour, count in sorted(hour_counter.items())
    ]

    return DiaryTimeStats(
        most_active_hour=most_active_hour,
        distribution=distribution,
    )


def calculate_top_menu(current_diaries: list[Diary]) -> TopMenu:
    """
    가장 많이 먹은 메뉴 계산 (뼈대만 구현)

    TODO: Gemini API를 사용해 note 필드에서 메뉴명 추출하거나
          tags 배열에서 메뉴 정보 추출

    Args:
        current_diaries: 이번 달 다이어리 목록

    Returns:
        TopMenu 모델 (현재는 placeholder)
    """
    return TopMenu(name="구현 예정", count=0)


def calculate_keywords(current_diaries: list[Diary]) -> list[str]:
    """
    사용자와 어울리는 키워드 생성 (뼈대만 구현)

    TODO: 식사 패턴, 카테고리, 태그를 분석하여 키워드 생성
          예: "혼밥러", "야식러버", "카페투어", "맛집탐방", "건강식러버"

    Args:
        current_diaries: 이번 달 다이어리 목록

    Returns:
        키워드 리스트 (현재는 빈 리스트)
    """
    return []


def get_month_date_range(year: int, month: int) -> tuple[datetime, datetime]:
    """
    주어진 년월의 시작일시와 종료일시를 반환

    Args:
        year: 년도
        month: 월 (1-12)

    Returns:
        (시작 datetime, 종료 datetime) 튜플 (timezone-aware UTC)
    """
    start_date = datetime(year, month, 1, tzinfo=UTC)

    # 다음 달 1일 계산
    if month == 12:
        end_date = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end_date = datetime(year, month + 1, 1, tzinfo=UTC)

    return start_date, end_date
