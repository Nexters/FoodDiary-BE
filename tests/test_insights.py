"""
Happy Path 테스트: /me/insights 엔드포인트
"""

from datetime import UTC, datetime

import pytest

from app.core.security import create_access_token
from app.models.diary import Diary
from app.models.user import User
from app.services.insights import MIN_DIARY_THRESHOLD
from tests.fixtures.auth_fixtures import create_test_user_data
from tests.fixtures.insights_fixtures import (
    create_current_month_diaries,
    create_previous_month_diaries,
)


class TestInsightsHappyPath:
    """Happy Path 테스트 모음 (정상 동작 시나리오)"""

    @pytest.mark.asyncio
    async def test_get_insights_with_sufficient_data(
        self,
        test_client,
        test_db_session,
    ):
        """
        정상 시나리오: 충분한 데이터로 통계를 성공적으로 반환

        Given: 이번 달 3개 이상의 다이어리 존재
        And: 저번 달 다이어리 존재
        When: /me/insights 호출
        Then: 200 OK + 통계 데이터 반환
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 이번 달 다이어리 생성 (3개)
        current_diaries_data = create_current_month_diaries(
            user.id, count=MIN_DIARY_THRESHOLD
        )
        for diary_data in current_diaries_data:
            diary = Diary(**diary_data)
            test_db_session.add(diary)

        # Given: 저번 달 다이어리 생성 (2개)
        previous_diaries_data = create_previous_month_diaries(user.id, count=2)
        for diary_data in previous_diaries_data:
            diary = Diary(**diary_data)
            test_db_session.add(diary)

        await test_db_session.commit()

        # Given: JWT 토큰 생성
        token = create_access_token(str(user.id), user.provider)

        # When: /me/insights 호출
        response = await test_client.get(
            "/me/insights",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 성공 응답
        assert response.status_code == 200
        data = response.json()

        # Then: 응답 구조 검증
        assert "month" in data
        assert "photo_stats" in data
        assert "category_stats" in data
        assert "top_menu" in data
        assert "diary_time_stats" in data
        assert "keywords" in data

        # Then: month 형식 검증
        now = datetime.now(UTC)
        expected_month = f"{now.year:04d}-{now.month:02d}"
        assert data["month"] == expected_month

    @pytest.mark.asyncio
    async def test_photo_stats_accurate_calculation(
        self,
        test_client,
        test_db_session,
    ):
        """
        사진 통계 정확도 검증

        Given: 이번 달 사진 18개 (5+6+7), 저번 달 사진 7개 (3+4)
        When: /me/insights 호출
        Then: 정확한 사진 수와 증감률 반환
        """
        # Given: 사용자 생성
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 이번 달 다이어리 (photo_count: 5, 6, 7)
        current_diaries = create_current_month_diaries(
            user.id, count=MIN_DIARY_THRESHOLD, base_photo_count=5
        )
        for diary_data in current_diaries:
            test_db_session.add(Diary(**diary_data))

        # Given: 저번 달 다이어리 (photo_count: 3, 4)
        previous_diaries = create_previous_month_diaries(
            user.id, count=2, base_photo_count=MIN_DIARY_THRESHOLD
        )
        for diary_data in previous_diaries:
            test_db_session.add(Diary(**diary_data))

        await test_db_session.commit()

        # Given: JWT 토큰
        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.get(
            "/me/insights",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then
        assert response.status_code == 200
        photo_stats = response.json()["photo_stats"]

        assert photo_stats["current_month_count"] == 18  # 5+6+7
        assert photo_stats["previous_month_count"] == 7  # 3+4
        # 증감률: ((18-7)/7)*100 = 157.14...
        assert photo_stats["change_rate"] == pytest.approx(157.1, abs=0.1)

    @pytest.mark.asyncio
    async def test_category_stats_most_frequent(
        self,
        test_client,
        test_db_session,
    ):
        """
        카테고리 통계 검증

        Given: 이번 달 한식 2회, 양식 1회
        When: /me/insights 호출
        Then: 가장 많이 먹은 카테고리 반환
        """
        # Given: 사용자
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        now = datetime.now(UTC)

        # Given: 이번 달 - 한식 2개
        for i in range(2):
            diary = Diary(
                user_id=user.id,
                diary_date=datetime(now.year, now.month, i + 1, 12, 0, tzinfo=UTC),
                category="한식",
                photo_count=5,
            )
            test_db_session.add(diary)

        # Given: 이번 달 - 양식 1개
        diary = Diary(
            user_id=user.id,
            diary_date=datetime(now.year, now.month, 10, 12, 0, tzinfo=UTC),
            category="양식",
            photo_count=MIN_DIARY_THRESHOLD,
        )
        test_db_session.add(diary)

        await test_db_session.commit()

        # Given: JWT 토큰
        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.get(
            "/me/insights",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then
        assert response.status_code == 200
        category_stats = response.json()["category_stats"]

        # 이번 달: 한식이 가장 많음
        assert category_stats["current_month"]["top_category"] == "한식"
        assert category_stats["current_month"]["count"] == 2

    @pytest.mark.asyncio
    async def test_deleted_diaries_excluded(
        self,
        test_client,
        test_db_session,
    ):
        """
        삭제된 다이어리 제외 검증

        Given: 이번 달 4개 다이어리 중 1개 삭제됨
        When: /me/insights 호출
        Then: 삭제되지 않은 3개만 통계에 반영
        """
        # Given: 사용자
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        now = datetime.now(UTC)

        # Given: 이번 달 다이어리 3개 (정상)
        for i in range(3):
            diary = Diary(
                user_id=user.id,
                diary_date=datetime(now.year, now.month, i + 1, 12, 0, tzinfo=UTC),
                category="한식",
                photo_count=5,
            )
            test_db_session.add(diary)

        # Given: 이번 달 다이어리 1개 (삭제됨)
        deleted_diary = Diary(
            user_id=user.id,
            diary_date=datetime(now.year, now.month, 20, 12, 0, tzinfo=UTC),
            category="한식",
            photo_count=100,  # 큰 숫자
            deleted_at=datetime.now(UTC),  # 삭제됨!
        )
        test_db_session.add(deleted_diary)

        await test_db_session.commit()

        # Given: JWT 토큰
        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.get(
            "/me/insights",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then
        assert response.status_code == 200
        photo_stats = response.json()["photo_stats"]

        # 삭제된 100장은 제외, 5*3=15장만 집계
        assert photo_stats["current_month_count"] == 15

    @pytest.mark.asyncio
    async def test_no_previous_month_data_handled(
        self,
        test_client,
        test_db_session,
    ):
        """
        저번 달 데이터 없는 경우 처리

        Given: 이번 달 데이터만 존재
        When: /me/insights 호출
        Then: 저번 달은 0으로, 증감률은 100%로 반환
        """
        # Given: 사용자
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 이번 달 다이어리만 생성
        current_diaries = create_current_month_diaries(
            user.id, count=MIN_DIARY_THRESHOLD
        )
        for diary_data in current_diaries:
            test_db_session.add(Diary(**diary_data))

        await test_db_session.commit()

        # Given: JWT 토큰
        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.get(
            "/me/insights",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then
        assert response.status_code == 200
        data = response.json()

        # 사진 통계
        photo_stats = data["photo_stats"]
        assert photo_stats["previous_month_count"] == 0
        assert photo_stats["change_rate"] == 100.0

        # 카테고리 통계
        category_stats = data["category_stats"]
        assert category_stats["previous_month"]["top_category"] == "데이터 없음"
        assert category_stats["previous_month"]["count"] == 0

    @pytest.mark.asyncio
    async def test_user_data_isolation(
        self,
        test_client,
        test_db_session,
    ):
        """
        사용자 간 데이터 격리 검증

        Given: 다른 사용자의 다이어리 존재
        When: 내 /me/insights 호출
        Then: 내 데이터만 통계에 반영
        """
        # Given: 내 계정
        my_user = User(
            **create_test_user_data(
                email="me@test.com",
                provider_user_id="me_123",
            )
        )
        test_db_session.add(my_user)

        # Given: 다른 사용자 계정
        other_user = User(
            **create_test_user_data(
                email="other@test.com",
                provider_user_id="other_456",
            )
        )
        test_db_session.add(other_user)

        await test_db_session.commit()
        await test_db_session.refresh(my_user)
        await test_db_session.refresh(other_user)

        now = datetime.now(UTC)

        # Given: 내 다이어리 (photo_count: 5+6+7=18)
        my_diaries = create_current_month_diaries(
            my_user.id, count=MIN_DIARY_THRESHOLD, base_photo_count=5
        )
        for diary_data in my_diaries:
            test_db_session.add(Diary(**diary_data))

        # Given: 다른 사용자의 다이어리 (photo_count: 100)
        other_diary = Diary(
            user_id=other_user.id,
            diary_date=datetime(now.year, now.month, 1, 12, 0, tzinfo=UTC),
            category="한식",
            photo_count=100,  # 많은 사진
        )
        test_db_session.add(other_diary)

        await test_db_session.commit()

        # Given: 내 JWT 토큰
        my_token = create_access_token(str(my_user.id), my_user.provider)

        # When: 내 계정으로 조회
        response = await test_client.get(
            "/me/insights",
            headers={"Authorization": f"Bearer {my_token}"},
        )

        # Then: 다른 사용자 데이터는 포함 안 됨
        assert response.status_code == 200
        photo_stats = response.json()["photo_stats"]

        # 내 사진만 (5+6+7=18), 다른 사용자의 100은 제외
        assert photo_stats["current_month_count"] == 18

    @pytest.mark.asyncio
    async def test_skeleton_features_return_placeholder(
        self,
        test_client,
        test_db_session,
    ):
        """
        뼈대 기능 플레이스홀더 검증

        Given: 정상 데이터 존재
        When: /me/insights 호출
        Then: top_menu는 "구현 예정", keywords는 빈 배열
        """
        # Given: 사용자 + 다이어리
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        current_diaries = create_current_month_diaries(
            user.id, count=MIN_DIARY_THRESHOLD
        )
        for diary_data in current_diaries:
            test_db_session.add(Diary(**diary_data))

        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.get(
            "/me/insights",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then
        assert response.status_code == 200
        data = response.json()

        # 뼈대 기능
        assert data["top_menu"]["name"] == "구현 예정"
        assert data["top_menu"]["count"] == 0
        assert data["keywords"] == []


class TestInsightsErrorCases:
    """에러 케이스 (30%: Happy Path가 아닌 경우)"""

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_400(
        self,
        test_client,
        test_db_session,
    ):
        """
        데이터 부족 시 400 에러

        Given: 이번 달 다이어리가 2개만 존재 (최소 3개 필요)
        When: /me/insights 호출
        Then: 400 Bad Request
        """
        # Given: 사용자
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 이번 달 다이어리 2개만 (임계값 3보다 작음)
        current_diaries = create_current_month_diaries(user.id, count=2)
        for diary_data in current_diaries:
            test_db_session.add(Diary(**diary_data))

        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.get(
            "/me/insights",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then
        assert response.status_code == 400
        assert "충분한 데이터가 없습니다" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_unauthorized_without_token(
        self,
        test_client,
    ):
        """
        인증 토큰 없이 호출 시 403

        When: Authorization 헤더 없이 /me/insights 호출
        Then: 403 Forbidden 접근 불가
        """
        # When: 토큰 없이 호출
        response = await test_client.get("/me/insights")

        # Then
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthorized_with_invalid_token(
        self,
        test_client,
    ):
        """
        유효하지 않은 토큰으로 호출 시 401

        When: 잘못된 JWT 토큰으로 /me/insights 호출
        Then: 401 Unauthorized
        """
        # When: 잘못된 토큰
        response = await test_client.get(
            "/me/insights",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )

        # Then
        assert response.status_code == 401
