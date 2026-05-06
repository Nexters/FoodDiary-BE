"""Diary 서비스 레이어"""

from datetime import datetime

from app.models import Diary
from app.utils.timezone import utc_to_kst

# 다이어리당 최대 사진 개수
MAX_PHOTOS_PER_DIARY = 10


def _build_tags(diary: Diary) -> list[str]:
    """Diary.tags 반환."""
    return diary.tags or []


def _merge_date_with_cover_taken_at(diary: Diary) -> datetime:
    """커버 사진의 taken_at 시각을 diary_date와 합쳐 KST datetime으로 반환.

    taken_at이 없으면 00:00:00으로 반환.
    """
    kst_date = utc_to_kst(diary.diary_date).date()
    time = (
        utc_to_kst(diary.cover_photo.taken_at).time()
        if diary.cover_photo and diary.cover_photo.taken_at
        else datetime.min.time()
    )
    return datetime.combine(kst_date, time)
