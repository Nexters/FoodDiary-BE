"""시간대 분류 유틸리티"""

from datetime import datetime

from app.schemas.diary import TimeType


def classify_time_type(taken_at: datetime | None) -> TimeType:
    """
    촬영 시간을 기준으로 끼니 타입을 분류합니다.

    시간대 분류 기준:
    - 05:00 ~ 10:00: breakfast (아침)
    - 10:00 ~ 14:00: lunch (점심)
    - 14:00 ~ 17:00: snack (간식)
    - 17:00 ~ 22:00: dinner (저녁)
    - 그 외: snack (간식)

    Args:
        taken_at: 촬영 시간 (None이면 기본값 'lunch' 반환)

    Returns:
        TimeType: 끼니 타입 ('breakfast', 'lunch', 'dinner', 'snack')
    """
    if taken_at is None:
        return "lunch"

    hour = taken_at.hour

    if 5 <= hour < 10:
        return "breakfast"
    elif 10 <= hour < 14:
        return "lunch"
    elif 14 <= hour < 17:
        return "snack"
    elif 17 <= hour < 22:
        return "dinner"
    else:
        return "snack"
