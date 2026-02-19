"""사용자 탈퇴 API 테스트"""

import shutil
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.device import Device
from app.models.diary import Diary
from app.models.user import User
from app.utils.file_storage import STORAGE_DIR
from tests.fixtures.auth_fixtures import create_test_user_data


@pytest.fixture
async def cleanup_user_storage():
    """테스트 전후 사용자 스토리지 디렉토리 정리"""
    yield
    if STORAGE_DIR.exists():
        shutil.rmtree(STORAGE_DIR)


class TestDeleteUserHappyPath:
    """회원 탈퇴 정상 케이스"""

    @pytest.mark.asyncio
    async def test_delete_user_succeeds(
        self,
        test_client,
        test_db_session: AsyncSession,
        cleanup_user_storage,
    ):
        """회원 탈퇴 시 204 반환, DB 및 스토리지 데이터 전부 삭제됨"""
        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()

        diary = Diary(
            user_id=user.id,
            diary_date=datetime(2024, 1, 15, tzinfo=UTC),
            time_type="lunch",
            restaurant_name="테스트 식당",
            category="한식",
        )
        device = Device(
            user_id=user.id,
            device_id="test-device-001",
            device_token="fcm-token-xyz",
            app_version="1.0.0",
            os_version="18.0",
            is_active=True,
        )
        test_db_session.add_all([diary, device])
        await test_db_session.commit()

        diary_id = diary.id
        device_id = device.id
        user_id = user.id

        user_dir = STORAGE_DIR / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "test.jpg").write_bytes(b"fake image")

        token = create_access_token(str(user_id), user.provider)

        # When
        response = await test_client.delete(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then
        assert response.status_code == 204

        user_result = await test_db_session.execute(
            select(User).where(User.id == user_id)
        )
        diary_result = await test_db_session.execute(
            select(Diary).where(Diary.id == diary_id)
        )
        device_result = await test_db_session.execute(
            select(Device).where(Device.id == device_id)
        )

        assert user_result.scalars().first() is None
        assert diary_result.scalars().first() is None
        assert device_result.scalars().first() is None
        assert not user_dir.exists()

    @pytest.mark.asyncio
    async def test_delete_user_without_storage_directory_succeeds(
        self,
        test_client,
        test_db_session: AsyncSession,
    ):
        """스토리지 디렉토리가 없어도 회원 탈퇴 성공"""
        # Given
        user = User(**create_test_user_data())
        test_db_session.add(user)
        await test_db_session.commit()

        assert not (STORAGE_DIR / str(user.id)).exists()

        token = create_access_token(str(user.id), user.provider)

        # When
        response = await test_client.delete(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then
        assert response.status_code == 204
