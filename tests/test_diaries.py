"""다이어리 API 테스트"""

from datetime import UTC, datetime

import pytest

from app.models.diary import Diary, DiaryAnalysis
from app.models.photo import Photo
from app.models.user import User
from app.services.jwt import create_access_token
from tests.fixtures.auth_fixtures import create_test_user_data
from tests.fixtures.diary_fixtures import (
    create_diary_analysis_data,
    create_diary_data,
    create_multiple_diaries_by_date,
    create_photo_data,
)


class TestGetDiaries:
    """GET /diaries 테스트 (날짜/기간별 조회)"""

    @pytest.mark.asyncio
    async def test_get_diaries_by_single_date(self, test_client, test_db_session):
        """
        단일 날짜로 다이어리 조회

        Given: 특정 날짜에 다이어리 1개 존재
        When: GET /diaries?start_date=2026-01-19&end_date=2026-01-19 호출
        Then: 해당 날짜의 다이어리 반환
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 다이어리 생성
        diary_data = create_diary_data(
            user_id=user.id,
            diary_date=datetime(2026, 1, 19, 12, 0, tzinfo=UTC),
            time_type="lunch",
            restaurant_name="맛집",
            category="korean",
            photo_count=2,
        )
        diary = Diary(**diary_data)
        test_db_session.add(diary)
        await test_db_session.commit()

        # Given: JWT 토큰 생성
        token = create_access_token(str(user.id), user.provider)

        # When: GET /diaries 호출 (일간 조회)
        response = await test_client.get(
            "/diaries?start_date=2026-01-19&end_date=2026-01-19",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 성공 응답
        assert response.status_code == 200
        data = response.json()

        # Then: 응답 구조 검증 (diaries 배열)
        assert "diaries" in data
        assert len(data["diaries"]) == 1

        diary_item = data["diaries"][0]
        assert diary_item["time_type"] == "lunch"
        assert diary_item["restaurant_name"] == "맛집"
        assert diary_item["category"] == "korean"
        assert diary_item["photo_count"] == 2

    @pytest.mark.asyncio
    async def test_get_diaries_by_date_range(self, test_client, test_db_session):
        """
        날짜 범위로 다이어리 사진 목록 조회 (캘린더 뷰용)

        Given: 여러 날짜에 다이어리 존재
        When: GET /diaries/summary?start_date=2026-01-15&end_date=2026-01-20 호출
        Then: 해당 범위의 모든 날짜 반환 (날짜별 photos URL 목록, 빈 날짜 포함)
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 여러 날짜의 다이어리 생성
        diaries_data = create_multiple_diaries_by_date(
            user.id,
            [
                ("2026-01-15", "breakfast"),
                ("2026-01-17", "lunch"),
                ("2026-01-20", "dinner"),
            ],
        )
        for diary_data in diaries_data:
            diary = Diary(**diary_data)
            test_db_session.add(diary)
        await test_db_session.commit()

        # Given: JWT 토큰 생성
        token = create_access_token(str(user.id), user.provider)

        # When: GET /diaries/summary 호출 (범위 조회)
        response = await test_client.get(
            "/diaries/summary?start_date=2026-01-15&end_date=2026-01-20",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 성공 응답
        assert response.status_code == 200
        data = response.json()

        # Then: 모든 날짜 포함 (빈 날짜도), 응답 형식은 날짜별 photos 배열
        assert "2026-01-15" in data
        assert "2026-01-16" in data  # 빈 날짜
        assert "2026-01-17" in data
        assert "2026-01-18" in data  # 빈 날짜
        assert "2026-01-19" in data  # 빈 날짜
        assert "2026-01-20" in data

        # Then: 날짜별 photos 배열 검증 (범위 조회는 photos URL 목록만 반환)
        # fixture는 다이어리만 생성하고 Photo 레코드는 없으므로 모두 리스트 형태만 검증
        for date_key in ("2026-01-15", "2026-01-16", "2026-01-17", "2026-01-20"):
            assert "photos" in data[date_key]
            assert isinstance(data[date_key]["photos"], list)
        assert len(data["2026-01-16"]["photos"]) == 0  # 다이어리 없는 날
        assert len(data["2026-01-18"]["photos"]) == 0
        assert len(data["2026-01-19"]["photos"]) == 0

    @pytest.mark.asyncio
    async def test_get_diaries_invalid_date_format(self, test_client, test_db_session):
        """
        잘못된 날짜 형식으로 조회 시 400 에러

        Given: 유효한 사용자
        When: GET /diaries?start_date=invalid-date&end_date=2026-01-19 호출
        Then: 400 Bad Request
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When: 잘못된 날짜 형식으로 조회 호출
        response = await test_client.get(
            "/diaries?start_date=invalid-date&end_date=2026-01-19",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 400 에러 (라우터에서 strptime 실패 시 400 반환)
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_diaries_date_range_too_long(self, test_client, test_db_session):
        """
        날짜 범위가 42일을 초과하면 400 에러

        Given: 유효한 사용자
        When: 43일 범위로 조회
        Then: 400 Bad Request
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When: 43일 범위로 호출
        response = await test_client.get(
            "/diaries/summary?start_date=2026-01-01&end_date=2026-02-13",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 400 에러
        assert response.status_code == 400
        assert "Date range must be within 42 days" in response.json()["detail"]


class TestGetDiaryById:
    """GET /diaries/{diary_id} 테스트 (상세 조회)"""

    @pytest.mark.asyncio
    async def test_get_diary_by_id_success(self, test_client, test_db_session):
        """
        다이어리 상세 조회 성공

        Given: 사용자의 다이어리와 사진 존재
        When: GET /diaries/{diary_id} 호출
        Then: 다이어리 상세 정보 반환 (사진 포함)
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 다이어리 생성
        diary_data = create_diary_data(
            user_id=user.id,
            restaurant_name="맛집",
            category="korean",
            note="맛있었어요",
            photo_count=2,
        )
        diary = Diary(**diary_data)
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        # Given: 사진 생성
        photo1_data = create_photo_data(diary.id, "https://example.com/photo1.jpg")
        photo2_data = create_photo_data(diary.id, "https://example.com/photo2.jpg")
        photo1 = Photo(**photo1_data)
        photo2 = Photo(**photo2_data)
        test_db_session.add_all([photo1, photo2])
        await test_db_session.commit()

        # Given: JWT 토큰 생성
        token = create_access_token(str(user.id), user.provider)

        # When: GET /diaries/{diary_id} 호출
        response = await test_client.get(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 성공 응답
        assert response.status_code == 200
        data = response.json()

        # Then: 다이어리 정보 검증
        assert data["id"] == diary.id
        assert data["restaurant_name"] == "맛집"
        assert data["category"] == "korean"
        assert data["note"] == "맛있었어요"
        assert data["photo_count"] == 2
        assert len(data["photos"]) == 2

    @pytest.mark.asyncio
    async def test_get_diary_by_id_not_found(self, test_client, test_db_session):
        """
        존재하지 않는 다이어리 조회 시 404 에러

        Given: 유효한 사용자
        When: 존재하지 않는 diary_id로 조회
        Then: 404 Not Found
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When: 존재하지 않는 다이어리 조회
        response = await test_client.get(
            "/diaries/99999",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 404 에러
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_diary_by_id_forbidden(self, test_client, test_db_session):
        """
        다른 사용자의 다이어리 조회 시 404 에러

        Given: 두 명의 사용자와 user1의 다이어리 존재
        When: user2가 user1의 다이어리 조회
        Then: 404 Not Found (권한 정보 노출 방지)
        """
        # Given: 사용자 1 생성
        user1_data = create_test_user_data(email="user1@example.com")
        user1 = User(**user1_data)
        test_db_session.add(user1)

        # Given: 사용자 2 생성
        user2_data = create_test_user_data(
            email="user2@example.com", provider_user_id="user_2"
        )
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user1)
        await test_db_session.refresh(user2)

        # Given: user1의 다이어리 생성
        diary_data = create_diary_data(user_id=user1.id)
        diary = Diary(**diary_data)
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        # Given: user2의 토큰 생성
        token = create_access_token(str(user2.id), user2.provider)

        # When: user2가 user1의 다이어리 조회
        response = await test_client.get(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 404 에러 (권한 정보 노출 방지)
        assert response.status_code == 404


class TestGetDiarySuggestions:
    """GET /diaries/{diary_id}/suggestions 테스트 (후보군 조회)"""

    @pytest.mark.asyncio
    async def test_get_diary_suggestions_success(self, test_client, test_db_session):
        """
        다이어리 후보군 조회 성공

        Given: 다이어리와 분석 결과 존재
        When: GET /diaries/{diary_id}/suggestions 호출
        Then: 식당/카테고리/메뉴 후보군 반환
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 다이어리 생성
        diary_data = create_diary_data(user_id=user.id)
        diary = Diary(**diary_data)
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        # Given: 분석 결과 생성
        analysis_data = create_diary_analysis_data(diary.id)
        analysis = DiaryAnalysis(**analysis_data)
        test_db_session.add(analysis)
        await test_db_session.commit()

        # Given: JWT 토큰 생성
        token = create_access_token(str(user.id), user.provider)

        # When: GET /diaries/{diary_id}/suggestions 호출
        response = await test_client.get(
            f"/diaries/{diary.id}/suggestions",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 성공 응답
        assert response.status_code == 200
        data = response.json()

        # Then: 후보군 검증
        assert "restaurants" in data
        assert len(data["restaurants"]) == 2
        assert data["restaurants"][0]["name"] == "맛집"
        assert data["restaurants"][0]["tags"] == ["김치찌개", "된장찌개"]
        assert data["restaurants"][0]["memo"] == "한식 전문점입니다."
        assert data["restaurants"][1]["name"] == "식당"

    @pytest.mark.asyncio
    async def test_get_diary_suggestions_no_analysis(
        self, test_client, test_db_session
    ):
        """
        분석 결과가 없는 다이어리 조회 시 빈 리스트 반환

        Given: 다이어리는 존재하지만 분석 결과 없음
        When: GET /diaries/{diary_id}/suggestions 호출
        Then: 200 OK with empty lists
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 다이어리 생성 (분석 결과 없음)
        diary_data = create_diary_data(user_id=user.id)
        diary = Diary(**diary_data)
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        token = create_access_token(str(user.id), user.provider)

        # When: 분석 결과 조회
        response = await test_client.get(
            f"/diaries/{diary.id}/suggestions",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 200 OK with empty list
        assert response.status_code == 200
        data = response.json()
        assert data["restaurants"] == []


class TestUpdateDiary:
    """PATCH /diaries/{diary_id} 테스트 (수정)"""

    @pytest.mark.asyncio
    async def test_update_diary_success(self, test_client, test_db_session):
        """
        다이어리 수정 성공

        Given: 사용자의 다이어리 존재
        When: PATCH /diaries/{diary_id} 호출
        Then: 다이어리 정보 업데이트
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 다이어리 생성
        diary_data = create_diary_data(
            user_id=user.id, restaurant_name="옛날 식당", category="korean"
        )
        diary = Diary(**diary_data)
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        token = create_access_token(str(user.id), user.provider)

        # When: PATCH /diaries/{diary_id} 호출
        response = await test_client.patch(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "restaurant_name": "새로운 식당",
                "category": "western",
                "note": "수정된 메모",
            },
        )

        # Then: 성공 응답
        assert response.status_code == 200
        data = response.json()

        # Then: 수정된 정보 검증
        assert data["restaurant_name"] == "새로운 식당"
        assert data["category"] == "western"
        assert data["note"] == "수정된 메모"

    @pytest.mark.asyncio
    async def test_update_diary_with_photo_ids(self, test_client, test_db_session):
        """
        다이어리 사진 삭제 (photo_ids 사용)

        Given: 다이어리에 3개의 사진 존재
        When: photo_ids로 2개만 지정 (나머지 1개는 삭제됨)
        Then: photo_count 업데이트되고, DB에서 실제로 삭제됨
        """
        from sqlalchemy import select

        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 다이어리 생성
        diary_data = create_diary_data(user_id=user.id, photo_count=3)
        diary = Diary(**diary_data)
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        # Given: 사진 3개 생성
        photos_data = [
            create_photo_data(diary.id, f"https://example.com/photo{i}.jpg")
            for i in range(1, 4)
        ]
        photos = [Photo(**pd) for pd in photos_data]
        test_db_session.add_all(photos)
        await test_db_session.commit()
        for photo in photos:
            await test_db_session.refresh(photo)

        token = create_access_token(str(user.id), user.provider)

        # ID 미리 저장 (expire_all 후 접근 방지)
        diary_id = diary.id
        photo_ids_to_keep = [photos[2].id, photos[0].id]
        photo_id_to_delete = photos[1].id

        # When: photo_ids로 3번, 1번만 유지 (2번 삭제)
        response = await test_client.patch(
            f"/diaries/{diary_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"photo_ids": photo_ids_to_keep},
        )

        # Then: 성공 응답
        assert response.status_code == 200
        data = response.json()

        # Then: photo_count 업데이트 확인
        assert data["photo_count"] == 2

        # Then: DB에서 실제로 사진 개수 확인 (세션 새로고침)
        test_db_session.expire_all()  # 캐시 비우기
        result = await test_db_session.execute(
            select(Photo).where(Photo.diary_id == diary_id)
        )
        remaining_photos = result.scalars().all()
        assert len(remaining_photos) == 2

        # Then: 삭제된 사진 확인
        remaining_photo_ids = {p.id for p in remaining_photos}
        assert photo_ids_to_keep[0] in remaining_photo_ids
        assert photo_ids_to_keep[1] in remaining_photo_ids
        assert photo_id_to_delete not in remaining_photo_ids  # 2번 사진은 삭제됨

    @pytest.mark.asyncio
    async def test_update_diary_not_found(self, test_client, test_db_session):
        """
        존재하지 않는 다이어리 수정 시 404 에러

        Given: 유효한 사용자
        When: 존재하지 않는 diary_id로 수정 요청
        Then: 404 Not Found
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When: 존재하지 않는 다이어리 수정
        response = await test_client.patch(
            "/diaries/99999",
            headers={"Authorization": f"Bearer {token}"},
            json={"restaurant_name": "새로운 식당"},
        )

        # Then: 404 에러
        assert response.status_code == 404


class TestDeleteDiary:
    """DELETE /diaries/{diary_id} 테스트 (삭제)"""

    @pytest.mark.asyncio
    async def test_delete_diary_success(self, test_client, test_db_session):
        """
        다이어리 삭제 성공 (소프트 삭제)

        Given: 사용자의 다이어리 존재
        When: DELETE /diaries/{diary_id} 호출
        Then: deleted_at 타임스탬프 설정
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Given: 다이어리 생성
        diary_data = create_diary_data(user_id=user.id)
        diary = Diary(**diary_data)
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        token = create_access_token(str(user.id), user.provider)

        # When: DELETE /diaries/{diary_id} 호출
        response = await test_client.delete(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 성공 응답
        assert response.status_code == 204

        # Then: 소프트 삭제 확인 (deleted_at 설정)
        await test_db_session.refresh(diary)
        assert diary.deleted_at is not None

    @pytest.mark.asyncio
    async def test_delete_diary_not_found(self, test_client, test_db_session):
        """
        존재하지 않는 다이어리 삭제 시 404 에러

        Given: 유효한 사용자
        When: 존재하지 않는 diary_id로 삭제 요청
        Then: 404 Not Found
        """
        # Given: 사용자 생성
        user_data = create_test_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When: 존재하지 않는 다이어리 삭제
        response = await test_client.delete(
            "/diaries/99999",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then: 404 에러
        assert response.status_code == 404
