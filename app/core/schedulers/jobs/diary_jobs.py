import logging

from app.core.database import AsyncSessionLocal
from app.crud.diary import get_pending_diaries
from app.usecases.diary import dispatch_pending_diary, expire_stale_diaries

logger = logging.getLogger(__name__)


async def run_expire_stale_diaries() -> None:
    count = await expire_stale_diaries()
    if count:
        logger.info("[DiaryScheduler] stale 복구: %d개 → pending", count)


async def run_handle_pending_diaries() -> None:
    async with AsyncSessionLocal() as db:
        pending = await get_pending_diaries(db)

    if not pending:
        return

    logger.info("[DiaryScheduler] pending 발견: %d개 분석 시작", len(pending))

    for diary in pending:
        try:
            await dispatch_pending_diary(diary.id)
        except Exception:
            logger.exception("[DiaryScheduler] diary_id=%d 처리 실패, 건너뜀", diary.id)
