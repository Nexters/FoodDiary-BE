"""
services/insights.py 서비스 함수 유닛 테스트 (DB 불필요)
"""

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from app.models.diary import Diary
from app.services.insights import (
    MIN_DIARY_THRESHOLD,
    _extract_dong,
    calculate_diary_time_stats,
    calculate_location_stats,
    calculate_tag_stats,
    calculate_weekly_stats,
    has_sufficient_data,
)
from app.utils.timezone import kst_naive_to_utc


def _kst(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """KST 시간을 UTC datetime으로 변환하는 테스트 헬퍼"""
    return kst_naive_to_utc(datetime(year, month, day, hour, minute))


def _make_diary(**kwargs) -> Diary:
    """DB 없이 테스트용 Diary 인스턴스 생성"""
    cover_photo = kwargs.pop("cover_photo", None)
    defaults = {
        "user_id": uuid4(),
        "diary_date": _kst(2025, 3, 1, 12, 0),
        "time_type": "lunch",
        "category": None,
        "photo_count": 1,
        "tags": [],
        "address_name": None,
    }
    defaults.update(kwargs)
    diary = Diary(**defaults)
    diary.cover_photo = cover_photo
    return diary


def _make_photo(taken_at: datetime | None = None) -> SimpleNamespace:
    """DB 없이 테스트용 Photo stub 생성"""
    return SimpleNamespace(taken_at=taken_at)


class TestExtractDong:
    """_extract_dong 함수 유닛 테스트"""

    def test_urban_dong_address(self):
        """도시 지번 주소에서 동 추출"""
        assert _extract_dong("서울 마포구 연남동 224-1") == "연남동"

    def test_rural_ri_address(self):
        """농어촌 지번 주소에서 리 추출"""
        assert _extract_dong("경기 양평군 양서면 양수리 456-78") == "양수리"

    def test_ga_suffix(self):
        """가로 끝나는 지번 주소 추출"""
        assert _extract_dong("서울 중구 을지로1가 12") == "을지로1가"

    def test_ro_suffix(self):
        """로로 끝나는 지번 주소 추출"""
        assert _extract_dong("서울 강남구 테헤란로 152") == "테헤란로"

    def test_no_dong_level_suffix(self):
        """동 수준 접미사 없으면 None 반환 (도로명 주소)"""
        assert _extract_dong("서울 강남구 선릉로126길 14") is None

    def test_no_lot_number_dong_suffix(self):
        """지번 없는 주소: 마지막 토큰이 동이면 반환"""
        assert _extract_dong("서울 강남구 역삼동") == "역삼동"

    def test_empty_string(self):
        """빈 문자열은 None 반환"""
        assert _extract_dong("") is None


def _make_diaries_on_distinct_days(day_count: int) -> list[Diary]:
    """서로 다른 KST 날짜에 각 1개씩 다이어리 생성"""
    return [
        _make_diary(diary_date=_kst(2025, 3, i + 1, 12, 0)) for i in range(day_count)
    ]


class TestHasSufficientData:
    """has_sufficient_data 함수 유닛 테스트 - 이번 달 7일 기준"""

    def test_returns_false_when_below_threshold(self):
        """7일 미만이면 False"""
        diaries = _make_diaries_on_distinct_days(MIN_DIARY_THRESHOLD - 1)
        assert has_sufficient_data(diaries) is False

    def test_returns_true_when_at_threshold(self):
        """정확히 7일이면 True"""
        diaries = _make_diaries_on_distinct_days(MIN_DIARY_THRESHOLD)
        assert has_sufficient_data(diaries) is True

    def test_returns_true_when_above_threshold(self):
        """7일 초과해도 True"""
        diaries = _make_diaries_on_distinct_days(MIN_DIARY_THRESHOLD + 5)
        assert has_sufficient_data(diaries) is True

    def test_returns_false_when_empty(self):
        """다이어리 없으면 False"""
        assert has_sufficient_data([]) is False

    def test_same_day_multiple_diaries_count_as_one_day(self):
        """같은 날 여러 끼니는 1일로 카운트 - 일기 수가 9개여도 3일이면 False"""
        diaries = [
            _make_diary(diary_date=_kst(2025, 3, (i // 3) + 1, 8 + (i % 3), 0))
            for i in range(9)  # 9개 다이어리, 3일치
        ]
        assert has_sufficient_data(diaries) is False


class TestCalculateTagStats:
    """calculate_tag_stats 함수 유닛 테스트"""

    def test_counts_tags_across_diaries(self):
        """여러 다이어리에 걸쳐 태그 빈도 집계"""
        diaries = [
            _make_diary(tags=["칼국수", "만두"]),
            _make_diary(tags=["칼국수", "라멘"]),
            _make_diary(tags=["만두"]),
        ]
        result = calculate_tag_stats(diaries)

        tag_map = {s.keyword: s.count for s in result}
        assert tag_map["칼국수"] == 2
        assert tag_map["만두"] == 2
        assert tag_map["라멘"] == 1

    def test_deduplicates_tags_within_diary(self):
        """한 다이어리 내 중복 태그는 1회로 계산"""
        diaries = [
            _make_diary(tags=["칼국수", "칼국수", "칼국수"]),
            _make_diary(tags=["칼국수"]),
        ]
        result = calculate_tag_stats(diaries)

        assert result[0].keyword == "칼국수"
        assert result[0].count == 2  # 다이어리 2개에 등장

    def test_sorted_by_count_desc(self):
        """빈도 내림차순 정렬"""
        diaries = [
            _make_diary(tags=["A"]),
            _make_diary(tags=["A"]),
            _make_diary(tags=["A"]),
            _make_diary(tags=["B"]),
            _make_diary(tags=["B"]),
            _make_diary(tags=["C"]),
        ]
        result = calculate_tag_stats(diaries)

        counts = [s.count for s in result]
        assert counts == sorted(counts, reverse=True)

    def test_returns_top_10_at_most(self):
        """최대 10개만 반환"""
        diaries = [_make_diary(tags=[f"태그{i}"]) for i in range(11)]
        result = calculate_tag_stats(diaries)
        assert len(result) <= 10

    def test_empty_tags_returns_empty(self):
        """태그 없는 다이어리만 있으면 빈 리스트 반환"""
        diaries = [_make_diary(tags=[]), _make_diary(tags=None)]
        result = calculate_tag_stats(diaries)
        assert result == []


class TestCalculateDiaryTimeStats:
    """calculate_diary_time_stats 함수 유닛 테스트"""

    def test_empty_returns_default(self):
        """다이어리 없으면 기본값 반환"""
        result = calculate_diary_time_stats([])
        assert result.most_active_time == "12:00"
        assert result.distribution == []

    def test_uses_cover_photo_taken_at(self):
        """cover_photo.taken_at이 있으면 해당 시간(KST 변환) 기준으로 집계"""
        diaries = [
            _make_diary(
                diary_date=_kst(2025, 3, 1, 9, 0),
                cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 19, 30)),
            ),
        ]
        result = calculate_diary_time_stats(diaries)
        assert result.most_active_time == "19:30"

    def test_falls_back_to_diary_date_when_no_cover_photo(self):
        """cover_photo가 없으면 diary_date(KST)로 fallback"""
        diaries = [
            _make_diary(diary_date=_kst(2025, 3, 1, 9, 5)),
        ]
        result = calculate_diary_time_stats(diaries)
        assert result.distribution[0].time == "09:00"
        assert result.most_active_time == "09:00"

    def test_falls_back_to_diary_date_when_taken_at_is_none(self):
        """cover_photo는 있지만 taken_at이 None이면 diary_date(KST)로 fallback"""
        diaries = [
            _make_diary(
                diary_date=_kst(2025, 3, 1, 9, 0),
                cover_photo=_make_photo(taken_at=None),
            ),
        ]
        result = calculate_diary_time_stats(diaries)
        assert result.most_active_time == "09:00"

    def test_time_slot_bucketed_to_30_min(self):
        """시간대를 30분 단위로 버킷 (KST 기준)"""
        diaries = [
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 12, 10))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 12, 45))),
        ]
        result = calculate_diary_time_stats(diaries)
        slots = {s.time for s in result.distribution}
        assert slots == {"12:00", "12:30"}

    def test_most_active_time_is_highest_count_slot(self):
        """most_active_time은 가장 많은 다이어리가 작성된 슬롯 (KST)"""
        diaries = [
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 21, 0))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 21, 20))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 21, 5))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 12, 0))),
        ]
        result = calculate_diary_time_stats(diaries)
        assert result.most_active_time == "21:00"

    def test_distribution_sorted_by_count_desc(self):
        """distribution은 횟수 내림차순 정렬"""
        diaries = [
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 21, 0))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 21, 10))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 21, 20))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 12, 0))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 12, 10))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 9, 0))),
        ]
        result = calculate_diary_time_stats(diaries)
        counts = [s.count for s in result.distribution]
        assert counts == sorted(counts, reverse=True)

    def test_returns_top_5_at_most(self):
        """최대 5개만 반환"""
        diaries = [
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, h, 0)))
            for h in range(7, 19)
        ]
        result = calculate_diary_time_stats(diaries)
        assert len(result.distribution) <= 5

    def test_same_slot_aggregated(self):
        """같은 30분 슬롯 내 다이어리는 count 합산 (KST)"""
        diaries = [
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 18, 0))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 18, 15))),
            _make_diary(cover_photo=_make_photo(taken_at=_kst(2025, 3, 1, 18, 29))),
        ]
        result = calculate_diary_time_stats(diaries)
        assert len(result.distribution) == 1
        assert result.distribution[0].time == "18:00"
        assert result.distribution[0].count == 3


class TestCalculateLocationStats:
    """calculate_location_stats 함수 유닛 테스트"""

    def test_counts_dong_from_address_name(self):
        """address_name에서 동을 추출해 집계"""
        diaries = [
            _make_diary(address_name="서울 마포구 연남동 224-1"),
            _make_diary(address_name="서울 마포구 연남동 100-5"),
            _make_diary(address_name="서울 강남구 역삼동 50-1"),
        ]
        result = calculate_location_stats(diaries)

        dong_map = {s.dong: s.count for s in result}
        assert dong_map["연남동"] == 2
        assert dong_map["역삼동"] == 1

    def test_skips_diaries_without_address_name(self):
        """address_name 없는 다이어리는 제외"""
        diaries = [
            _make_diary(address_name=None),
            _make_diary(address_name="서울 강남구 역삼동 123"),
        ]
        result = calculate_location_stats(diaries)
        assert len(result) == 1
        assert result[0].dong == "역삼동"

    def test_skips_addresses_without_dong_level(self):
        """동 수준 단위 없는 주소는 제외"""
        diaries = [
            _make_diary(address_name="서울 강남구 선릉로126길 14"),
            _make_diary(address_name="서울 강남구 역삼동 50"),
        ]
        result = calculate_location_stats(diaries)
        assert len(result) == 1
        assert result[0].dong == "역삼동"

    def test_sorted_by_count_desc(self):
        """빈도 내림차순 정렬"""
        diaries = [
            _make_diary(address_name="서울 마포구 연남동 1"),
            _make_diary(address_name="서울 마포구 연남동 2"),
            _make_diary(address_name="서울 마포구 연남동 3"),
            _make_diary(address_name="서울 강남구 역삼동 1"),
        ]
        result = calculate_location_stats(diaries)
        assert result[0].dong == "연남동"
        assert result[0].count == 3

    def test_returns_top_10_at_most(self):
        """최대 10개만 반환"""
        diaries = [
            _make_diary(address_name=f"서울 강남구 테스트{i}동 {i + 1}")
            for i in range(11)
        ]
        result = calculate_location_stats(diaries)
        assert len(result) <= 10


class TestCalculateWeeklyStats:
    """calculate_weekly_stats 함수 유닛 테스트"""

    def test_week_numbers_calculated_correctly(self):
        """주차 계산 정확성 검증 (KST 기준 1~7일=1주, 8~14일=2주, ...)"""
        diaries = [
            _make_diary(diary_date=_kst(2025, 3, 1, 12, 0)),  # 1주
            _make_diary(diary_date=_kst(2025, 3, 7, 12, 0)),  # 1주
            _make_diary(diary_date=_kst(2025, 3, 8, 12, 0)),  # 2주
            _make_diary(diary_date=_kst(2025, 3, 14, 12, 0)),  # 2주
            _make_diary(diary_date=_kst(2025, 3, 15, 12, 0)),  # 3주
        ]
        result = calculate_weekly_stats(diaries)

        week_map = {w.week: w.count for w in result.weekly_counts}
        assert week_map[1] == 2
        assert week_map[2] == 2
        assert week_map[3] == 1

    def test_most_active_week_is_highest_count(self):
        """most_active_week는 가장 많이 올린 주차"""
        diaries = [
            _make_diary(diary_date=_kst(2025, 3, 1, 12, 0)),  # 1주
            _make_diary(diary_date=_kst(2025, 3, 8, 12, 0)),  # 2주
            _make_diary(diary_date=_kst(2025, 3, 9, 12, 0)),  # 2주
            _make_diary(diary_date=_kst(2025, 3, 10, 12, 0)),  # 2주
        ]
        result = calculate_weekly_stats(diaries)
        assert result.most_active_week == 2

    def test_weekly_counts_sorted_by_week_asc(self):
        """weekly_counts는 주차 오름차순 정렬"""
        diaries = [
            _make_diary(diary_date=_kst(2025, 3, 22, 12, 0)),  # 4주
            _make_diary(diary_date=_kst(2025, 3, 8, 12, 0)),  # 2주
            _make_diary(diary_date=_kst(2025, 3, 1, 12, 0)),  # 1주
        ]
        result = calculate_weekly_stats(diaries)
        weeks = [w.week for w in result.weekly_counts]
        assert weeks == sorted(weeks)

    def test_empty_diaries_returns_default(self):
        """다이어리 없으면 most_active_week=1, weekly_counts=[]"""
        result = calculate_weekly_stats([])
        assert result.most_active_week == 1
        assert result.weekly_counts == []
