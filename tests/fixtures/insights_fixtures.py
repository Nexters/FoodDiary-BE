from datetime import date, datetime
from uuid import UUID

from app.utils.timezone import KST, kst_date_to_utc


def create_current_month_diaries(
    user_id: UUID,
    count: int = 7,
    base_photo_count: int = 5,
) -> list[dict]:
    """이번 달 다이어리 데이터 생성 (일별 1개, 기본 7일)"""
    now = datetime.now(KST)
    current_year = now.year
    current_month = now.month

    diaries = []
    categories = ["한식", "양식", "중식", "일식"]
    time_types = ["breakfast", "lunch", "dinner", "snack"]

    for i in range(count):
        diaries.append(
            {
                "user_id": user_id,
                "diary_date": kst_date_to_utc(date(current_year, current_month, i + 1)),
                "time_type": time_types[i % len(time_types)],
                "category": categories[i % len(categories)],
                "photo_count": base_photo_count + i,
                "note": f"테스트 노트 {i + 1}",
            }
        )

    return diaries


def create_previous_month_diaries(
    user_id: UUID,
    count: int = 2,
    base_photo_count: int = 3,
) -> list[dict]:
    """저번 달 다이어리 데이터 생성"""
    now = datetime.now(KST)
    current_year = now.year
    current_month = now.month

    # 저번 달 계산
    if current_month == 1:
        previous_year = current_year - 1
        previous_month = 12
    else:
        previous_year = current_year
        previous_month = current_month - 1

    diaries = []
    categories = ["양식", "중식"]
    time_types = ["lunch", "dinner"]

    for i in range(count):
        diaries.append(
            {
                "user_id": user_id,
                "diary_date": kst_date_to_utc(
                    date(previous_year, previous_month, (i * 10) + 1)
                ),
                "time_type": time_types[i % len(time_types)],
                "category": categories[i % len(categories)],
                "photo_count": base_photo_count + i,
                "note": f"저번 달 노트 {i + 1}",
            }
        )

    return diaries
