"""
음식점 검색 서비스 테스트
"""

import os
import uuid
from datetime import UTC, datetime

import pytest

from app.models.diary import Diary, DiaryAnalysis
from app.models.user import User
from app.schemas.restaurant import RestaurantSearchResponse
from app.usecases.restaurant import search_restaurants
from tests.fixtures.auth_fixtures import create_test_user_data

KAKAO_API_KEY_SET = bool(os.getenv("KAKAO_REST_API_KEY"))


class TestRestaurantServiceWithDB:
    """DB 기반 서비스 테스트"""

    @pytest.mark.asyncio
    async def test_diary_id_returns_restaurant_candidates(
        self,
        test_db_session,
    ):
        """
        diary_id로 음식점 후보 반환

        Given: 유저의 다이어리에 DiaryAnalysis가 존재
        When: diary_id로 search_restaurants 호출
        Then: restaurant_candidates가 RestaurantItem으로 반환됨
        """
        # Given: 사용자 생성
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 다이어리 생성
        diary = Diary(
            user_id=user.id,
            diary_date=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
            time_type="lunch",
            photo_count=1,
        )
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        # Given: DiaryAnalysis 생성
        analysis = DiaryAnalysis(
            diary_id=diary.id,
            result=[
                {
                    "restaurant_name": "명동교자",
                    "restaurant_url": "https://place.map.kakao.com/7942972",
                    "road_address": "서울 중구 명동10길 29",
                    "tags": ["칼국수"],
                    "category": "한식",
                    "memo": "",
                },
                {
                    "restaurant_name": "을지면옥",
                    "restaurant_url": "https://place.map.kakao.com/8001234",
                    "road_address": "서울 중구 을지로35길 10",
                    "tags": [],
                    "category": "한식",
                    "memo": "",
                },
            ],
        )
        test_db_session.add(analysis)
        await test_db_session.commit()

        # When
        result = await search_restaurants(
            session=test_db_session,
            user_id=user.id,
            diary_id=diary.id,
        )

        # Then
        assert isinstance(result, RestaurantSearchResponse)
        assert len(result.restaurants) == 2
        assert result.restaurants[0].name == "명동교자"
        assert result.restaurants[0].road_address == "서울 중구 명동10길 29"
        assert result.restaurants[0].url == "https://place.map.kakao.com/7942972"
        assert result.is_end is True

    @pytest.mark.asyncio
    async def test_nonexistent_diary_id_returns_empty(
        self,
        test_db_session,
    ):
        """
        존재하지 않는 diary_id → 빈 리스트

        Given: DB에 없는 diary_id
        When: search_restaurants 호출
        Then: 예외 없이 빈 리스트 반환
        """
        # Given: 사용자 생성
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # When
        result = await search_restaurants(
            session=test_db_session,
            user_id=user.id,
            diary_id=99999,
        )

        # Then
        assert result.restaurants == []
        assert result.is_end is True

    @pytest.mark.asyncio
    async def test_other_users_diary_returns_empty(
        self,
        test_db_session,
    ):
        """
        다른 유저의 diary_id → 빈 리스트

        Given: 다른 유저의 다이어리가 존재
        When: 내 user_id로 search_restaurants 호출
        Then: 빈 리스트 반환
        """
        # Given: 다른 사용자
        other_user = User(
            **create_test_user_data(
                provider_user_id="other_user_456",
                email="other@test.com",
            )
        )
        test_db_session.add(other_user)
        await test_db_session.commit()
        await test_db_session.refresh(other_user)

        # Given: 다른 사용자의 다이어리
        diary = Diary(
            user_id=other_user.id,
            diary_date=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
            time_type="lunch",
            photo_count=1,
        )
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        # Given: DiaryAnalysis
        analysis = DiaryAnalysis(
            diary_id=diary.id,
            result=[
                {
                    "restaurant_name": "명동교자",
                    "restaurant_url": "https://place.map.kakao.com/7942972",
                    "road_address": "서울 중구 명동10길 29",
                    "tags": [],
                    "category": "한식",
                    "memo": "",
                },
            ],
        )
        test_db_session.add(analysis)
        await test_db_session.commit()

        # When: 다른 유저 ID로 조회
        my_user_id = uuid.uuid4()
        result = await search_restaurants(
            session=test_db_session,
            user_id=my_user_id,
            diary_id=diary.id,
        )

        # Then
        assert result.restaurants == []

    @pytest.mark.asyncio
    async def test_no_params_returns_empty(
        self,
        test_db_session,
    ):
        """
        파라미터 없이 호출 → 빈 리스트

        When: diary_id, keyword 둘 다 없이 호출
        Then: 빈 리스트 반환
        """
        # When
        result = await search_restaurants(
            session=test_db_session,
            user_id=uuid.uuid4(),
        )

        # Then
        assert result.restaurants == []
        assert result.is_end is True

    @pytest.mark.asyncio
    async def test_candidates_without_required_fields_filtered(
        self,
        test_db_session,
    ):
        """
        필수 필드 없는 후보는 필터링됨

        Given: restaurant_candidates에 url 없는 항목 포함
        When: diary_id로 search_restaurants 호출
        Then: 필수 필드(name, road_address, url) 있는 항목만 반환
        """
        # Given: 사용자 + 다이어리
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        diary = Diary(
            user_id=user.id,
            diary_date=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
            time_type="lunch",
            photo_count=1,
        )
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        # Given: 일부 후보에 url 누락
        analysis = DiaryAnalysis(
            diary_id=diary.id,
            result=[
                {
                    "restaurant_name": "명동교자",
                    "restaurant_url": "https://place.map.kakao.com/7942972",
                    "road_address": "서울 중구 명동10길 29",
                    "tags": [],
                    "category": "한식",
                    "memo": "",
                },
                {
                    "restaurant_name": "불완전한 식당",
                    "restaurant_url": "",
                    "road_address": "",
                    "tags": [],
                    "category": "",
                    "memo": "",
                },
            ],
        )
        test_db_session.add(analysis)
        await test_db_session.commit()

        # When
        result = await search_restaurants(
            session=test_db_session,
            user_id=user.id,
            diary_id=diary.id,
        )

        # Then: url, road_address 빈 문자열인 항목은 필터링됨
        assert len(result.restaurants) == 1
        assert result.restaurants[0].name == "명동교자"


@pytest.mark.skipif(
    not KAKAO_API_KEY_SET,
    reason="KAKAO_REST_API_KEY 환경변수 미설정",
)
class TestKakaoKeywordSearch:
    """카카오 키워드 검색 테스트 (실제 API 호출)"""

    @pytest.mark.asyncio
    async def test_keyword_search_returns_restaurants(
        self,
        test_db_session,
    ):
        """
        keyword 검색 → 음식점 리스트 반환

        Given: 유효한 카카오 API 키
        When: keyword="명동교자"로 검색
        Then: 음식점 리스트 반환, 각 항목에 name/road_address/url 존재
        """
        # When
        result = await search_restaurants(
            session=test_db_session,
            user_id=uuid.uuid4(),
            keyword="명동교자",
        )

        # Then
        assert isinstance(result, RestaurantSearchResponse)
        assert len(result.restaurants) > 0
        assert result.page == 1
        assert result.size == 15

        first = result.restaurants[0]
        assert first.name
        assert first.url

    @pytest.mark.asyncio
    async def test_keyword_search_pagination(
        self,
        test_db_session,
    ):
        """
        페이지네이션 파라미터 전달 확인

        When: page=1, size=3으로 검색
        Then: 최대 3개 결과 반환
        """
        # When
        result = await search_restaurants(
            session=test_db_session,
            user_id=uuid.uuid4(),
            keyword="치킨",
            page=1,
            size=3,
        )

        # Then
        assert result.page == 1
        assert result.size == 3
        assert len(result.restaurants) <= 3

    @pytest.mark.asyncio
    async def test_keyword_overrides_diary_id(
        self,
        test_db_session,
    ):
        """
        keyword + diary_id → keyword만 사용

        Given: 유저의 다이어리에 분석 결과 존재
        When: keyword + diary_id로 호출
        Then: 카카오 검색 결과 반환 (diary_analysis 무시)
        """
        # Given: 사용자 + 다이어리 + 분석
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        diary = Diary(
            user_id=user.id,
            diary_date=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
            time_type="lunch",
            photo_count=1,
        )
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        analysis = DiaryAnalysis(
            diary_id=diary.id,
            result=[
                {
                    "restaurant_name": "DB에만_있는_식당",
                    "restaurant_url": "https://place.map.kakao.com/0000",
                    "road_address": "서울시 어딘가",
                    "tags": [],
                    "category": "한식",
                    "memo": "",
                },
            ],
        )
        test_db_session.add(analysis)
        await test_db_session.commit()

        # When: keyword + diary_id
        result = await search_restaurants(
            session=test_db_session,
            user_id=user.id,
            keyword="스타벅스",
            diary_id=diary.id,
        )

        # Then: 카카오 검색 결과 (DB 후보 "DB에만_있는_식당"이 아닌 카카오 결과)
        assert len(result.restaurants) > 0
        restaurant_names = [r.name for r in result.restaurants]
        assert "DB에만_있는_식당" not in restaurant_names
