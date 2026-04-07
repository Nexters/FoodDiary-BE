from datetime import UTC, date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def kst_date_to_utc(d: date) -> datetime:
    """KST 날짜 자정 → UTC datetime"""
    return datetime.combine(d, datetime.min.time(), tzinfo=KST).astimezone(UTC)


def kst_naive_to_utc(dt: datetime) -> datetime:
    """naive datetime(KST로 간주) → UTC aware datetime"""
    return dt.replace(tzinfo=KST).astimezone(UTC)


def utc_to_kst(dt: datetime) -> datetime:
    """UTC datetime → KST datetime (aware)"""
    return dt.astimezone(KST)


def utc_to_kst_naive(dt: datetime) -> datetime:
    """UTC datetime → KST naive datetime (offset 제거, FE 응답용)"""
    return dt.astimezone(KST).replace(tzinfo=None)
