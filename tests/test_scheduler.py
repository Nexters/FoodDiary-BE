"""스케줄러 핵심 로직 통합 테스트 — crud/usecase 함수 직접 검증"""

from datetime import UTC, datetime, timedelta

import pytest

from app.crud.diary import (
    claim_diary_for_processing,
    get_pending_diaries,
    get_stale_processing_diaries,
    mark_diaries_done,
    mark_diaries_failed,
    mark_diaries_pending,
)
from app.models import Diary
from app.models.user import User
from app.usecases.diary import exhaust_failed_diary
from tests.fixtures.auth_fixtures import create_test_user_data
from tests.fixtures.diary_fixtures import create_diary_data

# ========================================
# Helper
# ========================================

_TIME_TYPES = ("breakfast", "lunch", "dinner", "snack")
_diary_counter = 0


async def _create_diary(
    session,
    user_id,
    status: str,
    minutes_ago: int = 0,
    time_type: str | None = None,
    send_cnt: int = 0,
) -> Diary:
    """updated_at을 분 단위로 지정하여 다이어리 생성.

    time_type을 순환해 unique 제약 회피.
    updated_at이 stale 판단 기준이므로 created_at과 동일하게 설정.
    """
    global _diary_counter
    if time_type is None:
        time_type = _TIME_TYPES[_diary_counter % len(_TIME_TYPES)]
        _diary_counter += 1
    past_time = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    data = create_diary_data(
        user_id=user_id, analysis_status=status, time_type=time_type
    )
    data["created_at"] = past_time
    data["updated_at"] = past_time
    data["send_cnt"] = send_cnt
    diary = Diary(**data)
    session.add(diary)
    await session.flush()
    return diary


STALE_MINUTES = 5


# ========================================
# get_stale_processing_diaries 테스트
# ========================================


@pytest.mark.asyncio
async def test_stale_processing_diary_is_returned(test_db_session):
    """processing이면서 updated_at이 5분 이상 된 diary는 stale 목록에 포함된다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    await _create_diary(test_db_session, user.id, "processing", minutes_ago=6)

    stale_before = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES)
    stale = await get_stale_processing_diaries(test_db_session, stale_before)

    assert len(stale) == 1
    assert stale[0].analysis_status == "processing"


@pytest.mark.asyncio
async def test_recent_processing_diary_is_not_stale(test_db_session):
    """updated_at이 5분 미만인 processing diary는 stale 목록에 포함되지 않는다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    await _create_diary(test_db_session, user.id, "processing", minutes_ago=1)

    stale_before = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES)
    stale = await get_stale_processing_diaries(test_db_session, stale_before)

    assert len(stale) == 0


@pytest.mark.asyncio
async def test_done_diary_is_not_stale(test_db_session):
    """done diary는 아무리 오래돼도 stale 목록에 포함되지 않는다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    await _create_diary(test_db_session, user.id, "done", minutes_ago=60)

    stale_before = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES)
    stale = await get_stale_processing_diaries(test_db_session, stale_before)

    assert len(stale) == 0


@pytest.mark.asyncio
async def test_multiple_stale_diaries_all_returned(test_db_session):
    """stale processing diary 여러 개가 모두 반환된다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    for _ in range(2):
        await _create_diary(test_db_session, user.id, "processing", minutes_ago=10)

    stale_before = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES)
    stale = await get_stale_processing_diaries(test_db_session, stale_before)

    assert len(stale) == 2


# ========================================
# get_pending_diaries 테스트
# ========================================


@pytest.mark.asyncio
async def test_pending_diary_is_returned(test_db_session):
    """pending diary는 pending 목록에 포함된다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    await _create_diary(test_db_session, user.id, "pending")

    pending = await get_pending_diaries(test_db_session)

    assert len(pending) == 1
    assert pending[0].analysis_status == "pending"


@pytest.mark.asyncio
async def test_processing_diary_is_not_pending(test_db_session):
    """processing diary는 pending 목록에 포함되지 않는다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    await _create_diary(test_db_session, user.id, "processing")

    pending = await get_pending_diaries(test_db_session)

    assert len(pending) == 0


@pytest.mark.asyncio
async def test_done_and_failed_diary_is_not_pending(test_db_session):
    """done/failed diary는 pending 목록에 포함되지 않는다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    await _create_diary(test_db_session, user.id, "done", minutes_ago=60)
    await _create_diary(test_db_session, user.id, "failed", minutes_ago=60)

    pending = await get_pending_diaries(test_db_session)

    assert len(pending) == 0


# ========================================
# claim_diary_for_processing 테스트 (atomic claim)
# ========================================


@pytest.mark.asyncio
async def test_claim_pending_diary_succeeds(test_db_session):
    """pending diary를 claim하면 True 반환, status=processing, send_cnt가 1 증가한다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(test_db_session, user.id, "pending", send_cnt=0)

    result = await claim_diary_for_processing(test_db_session, diary.id)
    await test_db_session.refresh(diary)

    assert result is True
    assert diary.analysis_status == "processing"
    assert diary.send_cnt == 1


@pytest.mark.asyncio
async def test_claim_processing_diary_fails(test_db_session):
    """이미 processing인 diary는 claim이 실패한다 — False 반환, 상태/send_cnt 불변."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(test_db_session, user.id, "processing", send_cnt=1)

    result = await claim_diary_for_processing(test_db_session, diary.id)
    await test_db_session.refresh(diary)

    assert result is False
    assert diary.analysis_status == "processing"
    assert diary.send_cnt == 1


@pytest.mark.asyncio
async def test_concurrent_claim_only_one_succeeds(test_db_session):
    """같은 pending diary에 claim을 두 번 연속 시도하면 첫 번째만 성공한다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(test_db_session, user.id, "pending", send_cnt=0)

    first = await claim_diary_for_processing(test_db_session, diary.id)
    second = await claim_diary_for_processing(test_db_session, diary.id)

    assert first is True
    assert second is False


# ========================================
# 재시도 상태 전이 테스트
# ========================================


@pytest.mark.asyncio
async def test_stale_processing_below_max_returns_to_pending(test_db_session):
    """send_cnt가 MAX 미만인 stale processing diary는 pending으로 복귀한다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(
        test_db_session, user.id, "processing", minutes_ago=6, send_cnt=1
    )

    await mark_diaries_pending(test_db_session, [diary.id])
    await test_db_session.refresh(diary)

    assert diary.analysis_status == "pending"


@pytest.mark.asyncio
async def test_stale_processing_at_max_marks_failed(test_db_session):
    """send_cnt가 MAX 이상인 stale processing diary는 failed로 전환된다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(
        test_db_session, user.id, "processing", minutes_ago=6, send_cnt=3
    )

    await exhaust_failed_diary(test_db_session, diary.id)
    await test_db_session.refresh(diary)

    assert diary.analysis_status == "failed"


# ========================================
# 핵심 상태 전이 테스트
# ========================================


@pytest.mark.asyncio
async def test_pending_to_processing(test_db_session):
    """pending → claim → processing 전환이 정상 동작한다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(test_db_session, user.id, "pending", send_cnt=0)

    claimed = await claim_diary_for_processing(test_db_session, diary.id)
    await test_db_session.refresh(diary)

    assert claimed is True
    assert diary.analysis_status == "processing"
    assert diary.send_cnt == 1


@pytest.mark.asyncio
async def test_processing_to_pending_on_stale(test_db_session):
    """stale processing (send_cnt 미소진) → pending 복귀."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(
        test_db_session, user.id, "processing", minutes_ago=6, send_cnt=2
    )

    await mark_diaries_pending(test_db_session, [diary.id])
    await test_db_session.refresh(diary)

    assert diary.analysis_status == "pending"


@pytest.mark.asyncio
async def test_processing_to_failed_when_exhausted(test_db_session):
    """send_cnt >= MAX인 diary를 exhaust하면 failed로 전환된다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(
        test_db_session, user.id, "processing", minutes_ago=6, send_cnt=3
    )

    await exhaust_failed_diary(test_db_session, diary.id)
    await test_db_session.refresh(diary)

    assert diary.analysis_status == "failed"


@pytest.mark.asyncio
async def test_processing_to_done(test_db_session):
    """processing diary는 mark_diaries_done 호출 시 done으로 전환된다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(test_db_session, user.id, "processing")

    await mark_diaries_done(test_db_session, [diary.id])
    await test_db_session.refresh(diary)

    assert diary.analysis_status == "done"


# ========================================
# mark_diaries_done 테스트
# ========================================


@pytest.mark.asyncio
async def test_mark_diaries_done_updates_processing(test_db_session):
    """processing 상태 diary는 done으로 변경된다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(test_db_session, user.id, "processing", minutes_ago=1)

    await mark_diaries_done(test_db_session, [diary.id])
    await test_db_session.refresh(diary)

    assert diary.analysis_status == "done"


@pytest.mark.asyncio
async def test_mark_diaries_done_does_not_overwrite_failed(test_db_session):
    """failed 상태 diary에 mark_diaries_done을 호출해도 done으로 바뀌지 않는다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(test_db_session, user.id, "failed", minutes_ago=1)

    await mark_diaries_done(test_db_session, [diary.id])
    await test_db_session.refresh(diary)

    assert diary.analysis_status == "failed"


@pytest.mark.asyncio
async def test_mark_diaries_done_only_updates_processing(test_db_session):
    """혼재 상태에서 processing인 diary만 done으로 변경된다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    d_processing = await _create_diary(test_db_session, user.id, "processing", 1)
    d_done = await _create_diary(test_db_session, user.id, "done", 1)
    d_failed = await _create_diary(test_db_session, user.id, "failed", 1)
    d_pending = await _create_diary(test_db_session, user.id, "pending", 1)

    await mark_diaries_done(
        test_db_session,
        [d_processing.id, d_done.id, d_failed.id, d_pending.id],
    )

    for d in (d_processing, d_done, d_failed, d_pending):
        await test_db_session.refresh(d)

    assert d_processing.analysis_status == "done"
    assert d_done.analysis_status == "done"
    assert d_failed.analysis_status == "failed"
    assert d_pending.analysis_status == "pending"


# ========================================
# mark_diaries_failed 테스트
# ========================================


@pytest.mark.asyncio
async def test_mark_diaries_failed_updates_all(test_db_session):
    """mark_diaries_failed는 상태 무관하게 모두 failed로 변경한다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    d_processing = await _create_diary(test_db_session, user.id, "processing", 1)
    d_done = await _create_diary(test_db_session, user.id, "done", 1)
    d_pending = await _create_diary(test_db_session, user.id, "pending", 1)

    await mark_diaries_failed(
        test_db_session, [d_processing.id, d_done.id, d_pending.id]
    )

    for d in (d_processing, d_done, d_pending):
        await test_db_session.refresh(d)

    assert d_processing.analysis_status == "failed"
    assert d_done.analysis_status == "failed"
    assert d_pending.analysis_status == "failed"


# ========================================
# mark_diaries_pending 테스트
# ========================================


@pytest.mark.asyncio
async def test_mark_diaries_pending_resets_to_pending(test_db_session):
    """mark_diaries_pending은 processing diary를 pending으로 복귀시킨다."""
    user = User(**create_test_user_data())
    test_db_session.add(user)
    await test_db_session.flush()

    diary = await _create_diary(test_db_session, user.id, "processing")

    await mark_diaries_pending(test_db_session, [diary.id])
    await test_db_session.refresh(diary)

    assert diary.analysis_status == "pending"
