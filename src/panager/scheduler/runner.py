from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from panager.db.connection import get_pool

log = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler = AsyncIOScheduler()


def get_scheduler() -> AsyncIOScheduler:
    return _scheduler


async def send_scheduled_dm(
    bot,
    user_id: int,
    schedule_id: str,
    message: str,
    retry: int = 0,
) -> None:
    try:
        user = await bot.fetch_user(user_id)
        await user.send(message)
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE schedules SET sent = TRUE WHERE id = $1",
                UUID(schedule_id),
            )
        log.info(
            "알림 발송 완료", extra={"user_id": user_id, "schedule_id": schedule_id}
        )
    except Exception as e:
        if retry < 3:
            log.warning(
                "알림 발송 실패, 재시도", extra={"retry": retry, "error": str(e)}
            )
            await asyncio.sleep(2**retry)
            await send_scheduled_dm(bot, user_id, schedule_id, message, retry + 1)
        else:
            log.error("알림 발송 최대 재시도 초과", extra={"schedule_id": schedule_id})


async def restore_pending_schedules(bot) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, message, trigger_at
            FROM schedules
            WHERE sent = FALSE AND trigger_at > NOW()
            """
        )
    for row in rows:
        _scheduler.add_job(
            send_scheduled_dm,
            "date",
            run_date=row["trigger_at"],
            args=[bot, row["user_id"], str(row["id"]), row["message"]],
            id=str(row["id"]),
            replace_existing=True,
        )
    log.info("미발송 스케줄 복구 완료", extra={"count": len(rows)})
