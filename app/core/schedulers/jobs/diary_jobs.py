import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.core.database import AsyncSessionLocal
from app.crud.diary import get_pending_diaries, get_stale_processing_diaries
from app.crud.device import get_device_id_for_user
from app.usecases.diary import exhaust_failed_diary, expire_stale_diary
from app.usecases.photos import _background_tasks, analyze_and_notify

logger = logging.getLogger(__name__)

_STALE_THRESHOLD_MINUTES = 5
# 1회 초기 시도 + 재시도 2회 = 총 3회 시도
_MAX_SEND_CNT = 3


async def run_expire_stale_diaries() -> None:
    stale_before = datetime.now(UTC) - timedelta(minutes=_STALE_THRESHOLD_MINUTES)

    async with AsyncSessionLocal() as db:
        stale = await get_stale_processing_diaries(db, stale_before)

    if not stale:
        return

    logger.info("Scheduler: stale processing diaries found=%d", len(stale))

    # 부분 성공 허용: 하나 실패해도 나머지 diary는 계속 처리
    for diary in stale:
        try:
            async with AsyncSessionLocal() as db:
                if diary.send_cnt >= _MAX_SEND_CNT:
                    logger.info(
                        "Scheduler: stale diary id=%d exhausted all attempts, failing",
                        diary.id,
                    )
                    await exhaust_failed_diary(db, diary)
                else:
                    await expire_stale_diary(db, diary)
        except Exception:
            logger.exception("Failed to expire diary id=%d, skipping", diary.id)


async def run_handle_pending_diaries() -> None:
    async with AsyncSessionLocal() as db:
        pending = await get_pending_diaries(db)

    if not pending:
        return

    logger.info("Scheduler: pending diaries found=%d", len(pending))

    # 부분 성공 허용: 하나 실패해도 나머지 diary는 계속 처리
    for diary in pending:
        try:
            if diary.send_cnt < _MAX_SEND_CNT:
                logger.info(
                    "Scheduler: triggering analysis for diary id=%d (send_cnt=%d/%d)",
                    diary.id,
                    diary.send_cnt + 1,
                    _MAX_SEND_CNT,
                )
                async with AsyncSessionLocal() as db:
                    device_id = await get_device_id_for_user(db, diary.user_id)
                task = asyncio.create_task(
                    analyze_and_notify(
                        diary_ids=[diary.id],
                        device_id=device_id,
                        target_date=diary.diary_date.date(),
                    )
                )
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
            else:
                logger.info(
                    "Scheduler: diary id=%d exhausted all attempts, notifying",
                    diary.id,
                )
                async with AsyncSessionLocal() as db:
                    await exhaust_failed_diary(db, diary)
        except Exception:
            logger.exception(
                "Failed to handle pending diary id=%d, skipping", diary.id
            )
