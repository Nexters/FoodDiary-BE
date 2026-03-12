from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diary import Diary
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

MIN_DIARY_THRESHOLD = 7

_ALL_CATEGORIES = ("korean", "chinese", "japanese", "western", "etc", "home_cooked")
_DONG_LEVEL_SUFFIXES = ("동", "리", "가", "로")


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
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    current_year = now.year
    current_month = now.month

    current_range = get_month_date_range(current_year, current_month)

    if current_month == 1:
        previous_range = get_month_date_range(current_year - 1, 12)
    else:
        previous_range = get_month_date_range(current_year, current_month - 1)

    current_result = await session.execute(
        select(Diary).where(
            Diary.user_id == user_id,
            Diary.diary_date >= current_range[0],
            Diary.diary_date < current_range[1],
            Diary.deleted_at.is_(None),
        )
    )
    current_diaries = list(current_result.scalars().all())

    previous_result = await session.execute(
        select(Diary).where(
            Diary.user_id == user_id,
            Diary.diary_date >= previous_range[0],
            Diary.diary_date < previous_range[1],
            Diary.deleted_at.is_(None),
        )
    )
    previous_diaries = list(previous_result.scalars().all())

    _check_minimum_data(current_diaries)

    photo_stats = calculate_photo_stats(current_diaries, previous_diaries)
    category_stats = calculate_category_stats(current_diaries, previous_diaries)
    tag_stats = calculate_tag_stats(current_diaries)
    location_stats = calculate_location_stats(current_diaries)
    time_stats = calculate_diary_time_stats(current_diaries)
    weekly_stats = calculate_weekly_stats(current_diaries)

    return InsightsResponse(
        month=f"{current_year:04d}-{current_month:02d}",
        photo_stats=photo_stats,
        category_stats=category_stats,
        weekly_stats=weekly_stats,
        diary_time_stats=time_stats,
        tag_stats=tag_stats,
        location_stats=location_stats,
    )


def calculate_photo_stats(
    current_diaries: list[Diary],
    previous_diaries: list[Diary],
) -> PhotoStats:
    """사진 통계 계산 (이번 달 vs 저번 달)"""
    current_count = sum(d.photo_count for d in current_diaries)
    previous_count = sum(d.photo_count for d in previous_diaries)

    if previous_count > 0:
        change_rate = ((current_count - previous_count) / previous_count) * 100
    elif current_count > 0:
        change_rate = 100.0
    else:
        change_rate = 0.0

    return PhotoStats(
        current_month_count=current_count,
        previous_month_count=previous_count,
        change_rate=round(change_rate, 1),
    )


def calculate_category_stats(
    current_diaries: list[Diary],
    previous_diaries: list[Diary],
) -> CategoryStats:
    """카테고리 통계 계산 (최다 카테고리 + 전체 카운트)"""
    current_counter: Counter = Counter(
        d.category for d in current_diaries if d.category
    )
    previous_counter: Counter = Counter(
        d.category for d in previous_diaries if d.category
    )

    if current_counter:
        top_cat, cnt = current_counter.most_common(1)[0]
        current_info = CategoryInfo(top_category=top_cat, count=cnt)
    else:
        current_info = CategoryInfo(top_category="데이터 없음", count=0)

    if previous_counter:
        top_cat, cnt = previous_counter.most_common(1)[0]
        previous_info = CategoryInfo(top_category=top_cat, count=cnt)
    else:
        previous_info = CategoryInfo(top_category="데이터 없음", count=0)

    current_counts = CategoryCounts(
        **{cat: current_counter.get(cat, 0) for cat in _ALL_CATEGORIES}
    )

    return CategoryStats(
        current_month=current_info,
        previous_month=previous_info,
        current_month_counts=current_counts,
    )


def calculate_tag_stats(current_diaries: list[Diary]) -> list[TagStat]:
    """이번 달 태그 빈도 집계 (다이어리당 중복 제거 후 상위 10개)"""
    tag_counter: Counter = Counter()
    for diary in current_diaries:
        for tag in set(diary.tags or []):
            tag_counter[tag] += 1

    return [TagStat(keyword=tag, count=cnt) for tag, cnt in tag_counter.most_common(10)]


def calculate_location_stats(current_diaries: list[Diary]) -> list[LocationStat]:
    """이번 달 동 수준 장소 통계 (상위 10개)"""
    dong_counter: Counter = Counter()
    for diary in current_diaries:
        if diary.address_name:
            dong = _extract_dong(diary.address_name)
            if dong:
                dong_counter[dong] += 1

    return [
        LocationStat(dong=dong, count=cnt) for dong, cnt in dong_counter.most_common(10)
    ]


def calculate_diary_time_stats(current_diaries: list[Diary]) -> DiaryTimeStats:
    """일기 작성 시간대 통계 계산 (30분 단위)"""
    if not current_diaries:
        return DiaryTimeStats(most_active_time="12:00", distribution=[])

    slot_counter: Counter = Counter(
        f"{d.diary_date.hour:02d}:{(d.diary_date.minute // 30) * 30:02d}"
        for d in current_diaries
    )
    most_active_time = slot_counter.most_common(1)[0][0]
    distribution = [
        TimeSlotDistribution(time=slot, count=count)
        for slot, count in slot_counter.most_common(5)
    ]

    return DiaryTimeStats(most_active_time=most_active_time, distribution=distribution)


def calculate_weekly_stats(current_diaries: list[Diary]) -> WeeklyStats:
    """이번 달 주차별 다이어리 수 계산"""
    week_counter: Counter = Counter()
    for diary in current_diaries:
        week_num = (diary.diary_date.day - 1) // 7 + 1
        week_counter[week_num] += 1

    most_active_week = week_counter.most_common(1)[0][0] if week_counter else 1
    weekly_counts = [
        WeekStat(week=w, count=week_counter.get(w, 0))
        for w in sorted(week_counter.keys())
    ]

    return WeeklyStats(most_active_week=most_active_week, weekly_counts=weekly_counts)


def _check_minimum_data(diaries: list[Diary]) -> None:
    """데이터 최소 임계값 검사. 이번 달 7일 이상 기록해야 인사이트 제공."""
    unique_days = len({d.diary_date.date() for d in diaries})
    if unique_days < MIN_DIARY_THRESHOLD:
        raise InsufficientDataError(
            f"최소 {MIN_DIARY_THRESHOLD}일의 기록이 필요합니다 "
            f"(현재: {unique_days}일)"
        )


def _extract_dong(address_name: str) -> str | None:
    """지번 주소에서 동 수준 행정 단위 추출.

    지번(숫자 시작 토큰) 바로 앞 단어를 가져오고,
    동과 같은 급(동·리·가·로)으로 끝나는 경우 반환.

    예:
        '서울 마포구 연남동 224-1'      → '연남동'  (동)
        '경기 양평군 양서면 양수리 456'  → '양수리'  (리)
        '서울 강남구 역삼로 123'        → None (도로명은 동 수준 아님)
    """
    tokens = address_name.split()
    for i, token in enumerate(tokens):
        if token and token[0].isdigit():
            if i > 0 and tokens[i - 1].endswith(_DONG_LEVEL_SUFFIXES):
                return tokens[i - 1]
            return None
    if tokens and tokens[-1].endswith(_DONG_LEVEL_SUFFIXES):
        return tokens[-1]
    return None


def get_month_date_range(year: int, month: int) -> tuple[datetime, datetime]:
    """주어진 년월의 시작일시와 종료일시를 반환 (KST 기준)"""
    kst = timezone(timedelta(hours=9))
    start_date = datetime(year, month, 1, tzinfo=kst)

    if month == 12:
        end_date = datetime(year + 1, 1, 1, tzinfo=kst)
    else:
        end_date = datetime(year, month + 1, 1, tzinfo=kst)

    return start_date, end_date
