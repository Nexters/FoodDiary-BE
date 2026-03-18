"""다이어리 API 테스트"""

import asyncio
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
    async def test_update_diary_partial_update(self, test_client, test_db_session):
        """
        null 아닌 값만 업데이트 (partial update)

        Given: restaurant_name="기존 식당", note="기존 메모"인 다이어리, 사진 1개
        When: restaurant_name만 body에 포함 (note 미전송)
        Then: restaurant_name만 변경, note는 기존 값 유지
        """
        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        diary = Diary(
            **create_diary_data(
                user_id=user.id,
                restaurant_name="기존 식당",
                note="기존 메모",
                photo_count=1,
            )
        )
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        photo = Photo(**create_photo_data(diary.id, "storage/photo1.jpg"))
        test_db_session.add(photo)
        await test_db_session.commit()
        await test_db_session.refresh(photo)
        diary.cover_photo_id = photo.id
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When: restaurant_name만 전송, note 미전송
        response = await test_client.patch(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"restaurant_name": "새 식당", "photo_ids": [photo.id]},
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == diary.id
        assert data["restaurant_name"] == "새 식당"  # 변경됨
        assert data["note"] == "기존 메모"  # 미전송 → 기존 값 유지
        assert data["photo_count"] == 1
        assert data["cover_photo_id"] == photo.id

    @pytest.mark.asyncio
    async def test_update_diary_null_field_not_applied(
        self, test_client, test_db_session
    ):
        """
        명시적 null 필드는 업데이트하지 않음

        Given: note="기존 메모"인 다이어리
        When: {"note": null, "photo_ids": [...]} 전송
        Then: note는 기존 값 유지 (null → 무시)
        """
        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        diary = Diary(
            **create_diary_data(user_id=user.id, note="기존 메모", photo_count=1)
        )
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        photo = Photo(**create_photo_data(diary.id, "storage/photo1.jpg"))
        test_db_session.add(photo)
        await test_db_session.commit()
        await test_db_session.refresh(photo)
        diary.cover_photo_id = photo.id
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When: note를 명시적으로 null로 전송
        response = await test_client.patch(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"note": None, "photo_ids": [photo.id]},
        )

        # Then: null은 무시되어 기존 값 유지
        assert response.status_code == 200
        data = response.json()
        assert data["note"] == "기존 메모"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "body",
        [
            {"photo_ids": []},  # 빈 리스트
            {"photo_ids": [999999]},  # 존재하지 않는 ID
            {"restaurant_name": "새 식당"},  # photo_ids 미전송
        ],
        ids=["empty_list", "nonexistent_id", "no_photo_ids"],
    )
    async def test_update_diary_no_valid_photos(
        self, test_client, test_db_session, body
    ):
        """
        유효한 사진이 없는 경우 400

        Given: 사진 1개가 있는 다이어리
        When: photo_ids=[] / 없는 ID / photo_ids 미전송
        Then: 400 Bad Request (PhotoRequiredError)
        """
        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        diary = Diary(**create_diary_data(user_id=user.id, photo_count=1))
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        photo = Photo(**create_photo_data(diary.id, "storage/photo1.jpg"))
        test_db_session.add(photo)
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.patch(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )

        # Then
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_diary_remaining_photos(
        self, test_client, test_db_session, tmp_path
    ):
        """
        photo_ids 지정 → 남은 사진만 저장, 제외된 사진은 DB·파일에서 삭제

        Given: 사진 3개 (photo2는 실제 임시 파일), cover=photo1
        When: photo_ids=[photo1, photo3] (photo2 제외)
        Then:
          - 응답 photos={photo1, photo3}, photo_count=2
          - DB에서 photo2 사라짐
          - 실제 파일도 삭제됨
        """
        from sqlalchemy import select as sa_select

        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        diary = Diary(**create_diary_data(user_id=user.id, photo_count=3))
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        # photo2는 실제 임시 파일로 생성 (파일 삭제 검증용)
        tmp_file = tmp_path / "photo2.jpg"
        tmp_file.write_bytes(b"fake image data")

        photo1 = Photo(**create_photo_data(diary.id, "storage/photo1.jpg"))
        photo2 = Photo(**create_photo_data(diary.id, str(tmp_file)))
        photo3 = Photo(**create_photo_data(diary.id, "storage/photo3.jpg"))
        test_db_session.add_all([photo1, photo2, photo3])
        await test_db_session.commit()
        for p in [photo1, photo2, photo3]:
            await test_db_session.refresh(p)

        diary.cover_photo_id = photo1.id
        await test_db_session.commit()

        diary_id = diary.id
        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.patch(
            f"/diaries/{diary_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"photo_ids": [photo1.id, photo3.id]},
        )
        # 테스트에서는 override_get_session이 commit을 호출하지 않으므로
        # after_commit 이벤트가 발생하려면 명시적으로 commit 필요
        await test_db_session.commit()
        # commit 이후 create_task(delete_photo_files)가 실행될 시간 확보
        await asyncio.sleep(0.1)

        # Then: 응답 검증
        assert response.status_code == 200
        data = response.json()
        assert data["photo_count"] == 2
        response_photo_ids = {p["photo_id"] for p in data["photos"]}
        assert response_photo_ids == {photo1.id, photo3.id}

        # Then: DB 검증
        test_db_session.expire_all()
        result = await test_db_session.execute(
            sa_select(Photo).where(Photo.diary_id == diary_id)
        )
        remaining_ids = {p.id for p in result.scalars().all()}
        assert remaining_ids == {photo1.id, photo3.id}

        # Then: 실제 파일 삭제 검증
        assert not tmp_file.exists()

    @pytest.mark.asyncio
    async def test_update_diary_cover_photo_replaced(
        self, test_client, test_db_session
    ):
        """
        커버 사진이 photo_ids에서 제외되면 첫 번째 남은 사진으로 자동 교체

        Given: cover_photo_id=photo1, 사진 2개
        When: photo_ids=[photo2] (커버인 photo1 제외)
        Then: cover_photo_id=photo2로 교체
        """
        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        diary = Diary(**create_diary_data(user_id=user.id, photo_count=2))
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        photo1 = Photo(**create_photo_data(diary.id, "storage/photo1.jpg"))
        photo2 = Photo(**create_photo_data(diary.id, "storage/photo2.jpg"))
        test_db_session.add_all([photo1, photo2])
        await test_db_session.commit()
        await test_db_session.refresh(photo1)
        await test_db_session.refresh(photo2)

        diary.cover_photo_id = photo1.id
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When: 커버(photo1) 제외, photo2만 유지
        response = await test_client.patch(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"photo_ids": [photo2.id]},
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["cover_photo_id"] == photo2.id  # 자동 교체됨
        assert data["photo_count"] == 1

    @pytest.mark.asyncio
    async def test_update_diary_cover_photo_auto_set_when_none(
        self, test_client, test_db_session
    ):
        """
        cover_photo_id=None 상태에서 photo_ids 지정 시 첫 번째 사진으로 자동 설정

        Given: cover_photo_id=None인 다이어리, 사진 2개
        When: photo_ids=[photo1, photo2]
        Then: cover_photo_id=photo1 (photo_ids_ordered[0])으로 자동 설정
        """
        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # cover_photo_id=None (fixture 기본값)
        diary = Diary(**create_diary_data(user_id=user.id, photo_count=2))
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        photo1 = Photo(**create_photo_data(diary.id, "storage/photo1.jpg"))
        photo2 = Photo(**create_photo_data(diary.id, "storage/photo2.jpg"))
        test_db_session.add_all([photo1, photo2])
        await test_db_session.commit()
        await test_db_session.refresh(photo1)
        await test_db_session.refresh(photo2)

        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.patch(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"photo_ids": [photo1.id, photo2.id]},
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["cover_photo_id"] == photo1.id  # photo_ids_ordered[0]으로 자동 설정

    @pytest.mark.asyncio
    async def test_update_diary_not_found(self, test_client, test_db_session):
        """
        존재하지 않는 다이어리 수정 → 404

        Given: 유효한 사용자
        When: 존재하지 않는 diary_id로 수정
        Then: 404 Not Found
        """
        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.patch(
            "/diaries/99999",
            headers={"Authorization": f"Bearer {token}"},
            json={"restaurant_name": "새 식당", "photo_ids": [1]},
        )

        # Then
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_diary_forbidden(self, test_client, test_db_session):
        """
        다른 사용자의 다이어리 수정 → 404 (권한 정보 노출 방지)

        Given: user1의 다이어리, user2의 토큰
        When: user2가 user1의 다이어리 수정 시도
        Then: 404 Not Found
        """
        # Given
        user1 = User(**create_test_user_data(email="user1@example.com"))
        user2 = User(
            **create_test_user_data(
                email="user2@example.com", provider_user_id="user_2"
            )
        )
        test_db_session.add_all([user1, user2])
        await test_db_session.commit()
        await test_db_session.refresh(user1)
        await test_db_session.refresh(user2)

        diary = Diary(**create_diary_data(user_id=user1.id, photo_count=1))
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        photo = Photo(**create_photo_data(diary.id, "storage/photo1.jpg"))
        test_db_session.add(photo)
        await test_db_session.commit()
        await test_db_session.refresh(photo)
        diary.cover_photo_id = photo.id
        await test_db_session.commit()

        token = create_access_token(str(user2.id), user2.provider)

        # When: user2가 user1의 다이어리 수정 시도
        response = await test_client.patch(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"restaurant_name": "새 식당", "photo_ids": [photo.id]},
        )

        # Then
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_diary_mixed_photo_ids(self, test_client, test_db_session):
        """
        유효/무효 혼합 photo_ids → 유효한 것만 남음

        Given: 사진 2개 (photo1, photo2)
        When: photo_ids=[photo1.id, 99999] (유효 1개 + 없는 ID 1개)
        Then: photo1만 남음, photo2 삭제됨, photo_count=1
        """
        from sqlalchemy import select as sa_select

        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        diary = Diary(**create_diary_data(user_id=user.id, photo_count=2))
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        photo1 = Photo(**create_photo_data(diary.id, "storage/photo1.jpg"))
        photo2 = Photo(**create_photo_data(diary.id, "storage/photo2.jpg"))
        test_db_session.add_all([photo1, photo2])
        await test_db_session.commit()
        await test_db_session.refresh(photo1)
        await test_db_session.refresh(photo2)

        diary.cover_photo_id = photo1.id
        await test_db_session.commit()

        diary_id = diary.id
        token = create_access_token(str(user.id), user.provider)

        # When: 유효한 photo1 + 없는 ID 99999
        response = await test_client.patch(
            f"/diaries/{diary_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"photo_ids": [photo1.id, 99999]},
        )

        # Then: 응답
        assert response.status_code == 200
        data = response.json()
        assert data["photo_count"] == 1
        assert data["photos"][0]["photo_id"] == photo1.id

        # Then: DB — photo2 삭제됨
        test_db_session.expire_all()
        result = await test_db_session.execute(
            sa_select(Photo).where(Photo.diary_id == diary_id)
        )
        remaining_ids = {p.id for p in result.scalars().all()}
        assert remaining_ids == {photo1.id}

    @pytest.mark.asyncio
    async def test_update_diary_file_not_deleted_on_rollback(
        self, test_client, test_db_session, tmp_path
    ):
        """
        커밋이 이루어지지 않으면 (롤백 시) 파일이 삭제되지 않음

        after_commit 이벤트를 통해 파일 삭제를 예약하므로,
        세션이 커밋되지 않으면 이벤트가 발화하지 않아 파일은 보존됨.

        Given: 실제 파일이 있는 사진 2개 (photo2가 삭제 대상)
        When: PATCH 성공 (200) 하지만 session.commit() 미호출
        Then: tmp_file.exists() == True  ← 커밋 없이는 파일 삭제 안됨
        """
        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        diary = Diary(**create_diary_data(user_id=user.id, photo_count=2))
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        tmp_file = tmp_path / "photo2.jpg"
        tmp_file.write_bytes(b"fake image data")

        photo1 = Photo(**create_photo_data(diary.id, "storage/photo1.jpg"))
        photo2 = Photo(**create_photo_data(diary.id, str(tmp_file)))
        test_db_session.add_all([photo1, photo2])
        await test_db_session.commit()
        await test_db_session.refresh(photo1)
        await test_db_session.refresh(photo2)

        diary.cover_photo_id = photo1.id
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When: PATCH 성공 (200), 하지만 test_db_session.commit()은 호출하지 않음
        response = await test_client.patch(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"photo_ids": [photo1.id]},
        )
        await asyncio.sleep(0.1)  # after_commit 이벤트가 발화할 시간 대기

        # Then
        assert response.status_code == 200
        assert tmp_file.exists()  # 커밋이 없으므로 after_commit 미발화 → 파일 보존

    @pytest.mark.asyncio
    async def test_update_diary_soft_deleted(self, test_client, test_db_session):
        """
        소프트 삭제된 다이어리 수정 → 404

        Given: deleted_at이 설정된 다이어리
        When: PATCH
        Then: 404 (crud의 deleted_at.is_(None) 필터)
        """
        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        diary_data = create_diary_data(user_id=user.id, photo_count=1)
        diary_data["deleted_at"] = datetime.now(UTC)  # 소프트 삭제 처리
        diary = Diary(**diary_data)
        test_db_session.add(diary)
        await test_db_session.commit()
        await test_db_session.refresh(diary)

        photo = Photo(**create_photo_data(diary.id, "storage/photo1.jpg"))
        test_db_session.add(photo)
        await test_db_session.commit()

        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.patch(
            f"/diaries/{diary.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"photo_ids": [photo.id]},
        )

        # Then
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
