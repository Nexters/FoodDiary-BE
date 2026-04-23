"""스케줄러 핵심 로직 통합 테스트 — crud 함수 직접 검증"""

from datetime import UTC, datetime, timedelta

import pytest

from app.crud.diary import (
    get_stale_processing_diaries,
    mark_diaries_done,
    mark_diaries_failed,
)
from app.models import Diary
from app.models.user import User
from tests.fixtures.auth_fixtures import create_test_user_data
from tests.fixtures.diary_fixtures import create_diary_data

# ========================================
# Helper
# ========================================


_TIME_TYPES = ("breakfast", "lunch", "dinner", "snack")
_diary_counter = 0


async def _create_diary(
    session, user_id, status: str, minutes_ago: int, time_type: str | None = None
) -> Diary:
    """분 단위로 생성 시각을 지정하여 다이어리 생성. time_type을 순환해 unique 제약 회피."""  # noqa: E501
    global _diary_counter
    if time_type is None:
        time_type = _TIME_TYPES[_diary_counter % len(_TIME_TYPES)]
        _diary_counter += 1
    created_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    data = create_diary_data(
        user_id=user_id, analysis_status=status, time_type=time_type
    )
    data["created_at"] = created_at
    diary = Diary(**data)
    session.add(diary)
    await session.flush()
    return diary


STALE_MINUTES = 5  # 스케줄러 만료 임계값


# ========================================
# get_stale_processing_diaries 테스트
# ========================================


@pytest.mark.asyncio
async def test_stale_processing_diary_is_returned(test_db_session):
    """
    5분 이상 된 processing 다이어리는 stale 목록에 포함된다.
    """
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    await _create_diary(test_db_session, user.id, "processing", minutes_ago=6)

    stale_before = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES)
    stale = await get_stale_processing_diaries(test_db_session, stale_before)

    assert len(stale) == 1
    assert stale[0].analysis_status == "processing"


@pytest.mark.asyncio
async def test_recent_processing_diary_is_not_returned(test_db_session):
    """
    5분 미만 processing 다이어리는 stale 목록에 포함되지 않는다.
    """
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    await _create_diary(test_db_session, user.id, "processing", minutes_ago=1)

    stale_before = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES)
    stale = await get_stale_processing_diaries(test_db_session, stale_before)

    assert len(stale) == 0


@pytest.mark.asyncio
async def test_done_diary_is_not_returned(test_db_session):
    """
    done 다이어리는 아무리 오래돼도 stale 목록에 포함되지 않는다.
    """
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    await _create_diary(test_db_session, user.id, "done", minutes_ago=60)

    stale_before = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES)
    stale = await get_stale_processing_diaries(test_db_session, stale_before)

    assert len(stale) == 0


@pytest.mark.asyncio
async def test_multiple_stale_diaries_all_returned(test_db_session):
    """
    stale processing 다이어리 여러 개가 모두 반환된다.
    """
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    for _ in range(3):
        await _create_diary(test_db_session, user.id, "processing", minutes_ago=10)

    stale_before = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES)
    stale = await get_stale_processing_diaries(test_db_session, stale_before)

    assert len(stale) == 3


# ========================================
# mark_diaries_done 테스트
# ========================================


@pytest.mark.asyncio
async def test_mark_diaries_done_updates_processing(test_db_session):
    """
    processing 상태 다이어리는 done으로 변경된다.
    """
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(test_db_session, user.id, "processing", minutes_ago=1)

    await mark_diaries_done(test_db_session, [diary.id])
    await test_db_session.refresh(diary)

    assert diary.analysis_status == "done"


@pytest.mark.asyncio
async def test_mark_diaries_done_does_not_overwrite_failed(test_db_session):
    """
    이미 failed 상태인 다이어리에 mark_diaries_done을 호출해도 done으로 바뀌지 않는다.
    스케줄러가 먼저 failed 처리한 뒤 백그라운드 태스크가 완료되는 경쟁 상황을 방지.
    """
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(test_db_session, user.id, "failed", minutes_ago=1)

    await mark_diaries_done(test_db_session, [diary.id])
    await test_db_session.refresh(diary)

    assert diary.analysis_status == "failed"  # 변경되지 않아야 함


@pytest.mark.asyncio
async def test_mark_diaries_done_only_updates_processing(test_db_session):
    """
    processing / done / failed 다이어리가 섞여 있을 때,
    mark_diaries_done은 processing인 것만 done으로 변경한다.
    """
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    d_processing = await _create_diary(test_db_session, user.id, "processing", 1)
    d_done = await _create_diary(test_db_session, user.id, "done", 1)
    d_failed = await _create_diary(test_db_session, user.id, "failed", 1)

    await mark_diaries_done(test_db_session, [d_processing.id, d_done.id, d_failed.id])

    await test_db_session.refresh(d_processing)
    await test_db_session.refresh(d_done)
    await test_db_session.refresh(d_failed)

    assert d_processing.analysis_status == "done"
    assert d_done.analysis_status == "done"  # 이미 done → 유지
    assert d_failed.analysis_status == "failed"  # failed → 변경 안 됨


# ========================================
# mark_diaries_failed 테스트
# ========================================


@pytest.mark.asyncio
async def test_mark_diaries_failed_updates_all(test_db_session):
    """
    mark_diaries_failed는 processing / done 상관없이 모두 failed로 변경한다.
    """
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    d_processing = await _create_diary(test_db_session, user.id, "processing", 1)
    d_done = await _create_diary(test_db_session, user.id, "done", 1)

    await mark_diaries_failed(test_db_session, [d_processing.id, d_done.id])

    await test_db_session.refresh(d_processing)
    await test_db_session.refresh(d_done)

    assert d_processing.analysis_status == "failed"
    assert d_done.analysis_status == "failed"
