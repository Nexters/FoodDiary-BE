import asyncio
import logging

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.schedulers.executor import scheduler
from app.core.schedulers.jobs.diary_jobs import (
    run_expire_stale_diaries,
    run_handle_pending_diaries,
)

logger = logging.getLogger(__name__)

_INTERVAL_SECONDS = 60
_SCHEDULER_LOCK_NAME = "diary-scheduler"


@scheduler
def start_diary_scheduler() -> asyncio.Task:
    return asyncio.create_task(_scheduler_loop(), name="diary-scheduler")


async def _scheduler_loop() -> None:
    logger.info(
        "Diary scheduler started (interval=%ds)",
        _INTERVAL_SECONDS,
    )
    while True:
        await asyncio.sleep(_INTERVAL_SECONDS)
        async with AsyncSessionLocal() as db:
            acquired = await _try_acquire_lock(db)
            if not acquired:
                logger.debug("Scheduler lock not acquired, skipping this tick")
                continue
            try:
                await run_expire_stale_diaries()
                await run_handle_pending_diaries()
            except Exception:
                logger.exception("Scheduler error during diary scheduler jobs")
            finally:
                await _release_lock(db)



async def _try_acquire_lock(db_conn) -> bool:
    """pg_try_advisory_lock으로 분산 락 시도. 획득 실패 시 False 반환."""
    result = await db_conn.execute(
        text("SELECT pg_try_advisory_lock(hashtext(:lock_name))"),
        {"lock_name": _SCHEDULER_LOCK_NAME},
    )
    return result.scalar()


async def _release_lock(db_conn) -> None:
    await db_conn.execute(
        text("SELECT pg_advisory_unlock(hashtext(:lock_name))"),
        {"lock_name": _SCHEDULER_LOCK_NAME},
    )
