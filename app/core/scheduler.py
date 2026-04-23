"""asyncio 기반 다이어리 만료 스케줄러"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.crud.device import get_device_id_for_user
from app.crud.diary import get_stale_processing_diaries, mark_diaries_failed
from app.services.notification_service import send_silent_notification

logger = logging.getLogger(__name__)

_INTERVAL_SECONDS = 60
_STALE_THRESHOLD_MINUTES = 5
_SCHEDULER_LOCK_ID = 20240101  # 고정 Advisory Lock ID


async def _expire_stale_diaries() -> None:
    stale_before = datetime.now(UTC) - timedelta(minutes=_STALE_THRESHOLD_MINUTES)

    async with AsyncSessionLocal() as db:
        stale = await get_stale_processing_diaries(db, stale_before)

    if not stale:
        return

    logger.info("Scheduler: stale processing diaries found=%d", len(stale))

    for diary in stale:
        async with AsyncSessionLocal() as db:
            await mark_diaries_failed(db, [diary.id])
            await db.commit()
            device_id = await get_device_id_for_user(db, diary.user_id)
            await send_silent_notification(
                db=db,
                device_id=device_id,
                data={
                    "type": "analysis_failed",
                    "diary_date": str(diary.diary_date.date()),
                },
            )


async def _try_acquire_lock(db_conn) -> bool:
    """pg_try_advisory_lock으로 분산 락 시도. 획득 실패 시 False 반환."""
    result = await db_conn.execute(
        text("SELECT pg_try_advisory_lock(:lock_id)"),
        {"lock_id": _SCHEDULER_LOCK_ID},
    )
    return result.scalar()


async def _release_lock(db_conn) -> None:
    await db_conn.execute(
        text("SELECT pg_advisory_unlock(:lock_id)"),
        {"lock_id": _SCHEDULER_LOCK_ID},
    )


async def _scheduler_loop() -> None:
    logger.info(
        "Diary scheduler started (interval=%ds, stale_threshold=%dmin)",
        _INTERVAL_SECONDS,
        _STALE_THRESHOLD_MINUTES,
    )
    while True:
        await asyncio.sleep(_INTERVAL_SECONDS)
        async with AsyncSessionLocal() as db:
            acquired = await _try_acquire_lock(db)
            if not acquired:
                logger.debug("Scheduler lock not acquired, skipping this tick")
                continue
            try:
                await _expire_stale_diaries()
            except Exception:
                logger.exception("Scheduler error during _expire_stale_diaries")
            finally:
                await _release_lock(db)


def start_scheduler() -> asyncio.Task:
    return asyncio.create_task(_scheduler_loop(), name="diary-scheduler")
