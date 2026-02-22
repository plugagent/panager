from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Protocol, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    import asyncpg
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger(__name__)


class NotificationProvider(Protocol):
    """알림 발송을 위한 인터페이스."""

    async def send_notification(self, user_id: int, message: str) -> None: ...


class SchedulerService:
    """APScheduler와 DB 연동을 담당하는 서비스."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        notification_provider: NotificationProvider | None = None,
    ) -> None:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self._pool = pool
        self._notification_provider = notification_provider
        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()

    def set_notification_provider(self, provider: NotificationProvider) -> None:
        """알림 제공자를 설정합니다."""
        self._notification_provider = provider

    async def add_schedule(
        self, user_id: int, message: str, trigger_at: datetime
    ) -> UUID:
        """새로운 알림 일정을 추가하고 스케줄러에 등록합니다."""
        async with self._pool.acquire() as conn:
            schedule_id = await conn.fetchval(
                """
                INSERT INTO schedules (user_id, message, trigger_at)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                user_id,
                message,
                trigger_at,
            )

        sid_str = str(schedule_id)
        self._scheduler.add_job(
            self._send_scheduled_dm,
            "date",
            run_date=trigger_at,
            args=[user_id, sid_str, message],
            id=sid_str,
            replace_existing=True,
        )
        return UUID(sid_str)

    async def cancel_schedule(self, user_id: int, schedule_id: str) -> bool:
        """예약된 알림 일정을 취소합니다."""
        async with self._pool.acquire() as conn:
            # user_id를 확인하여 본인의 일정만 삭제 가능하도록 함
            result = await conn.execute(
                "DELETE FROM schedules WHERE id = $1 AND user_id = $2",
                UUID(schedule_id),
                user_id,
            )
            # result는 "DELETE 1"과 같은 형태
            rows_affected = int(result.split()[-1])

        if rows_affected > 0:
            try:
                self._scheduler.remove_job(schedule_id)
                return True
            except Exception:
                # 이미 실행되었거나 없는 경우
                return True
        return False

    async def _send_scheduled_dm(
        self, user_id: int, schedule_id: str, message: str, retry: int = 0
    ) -> None:
        """스케줄러에 의해 호출되어 실제 알림을 발송합니다."""
        if self._notification_provider is None:
            log.error(
                "알림 제공자가 설정되지 않아 알림을 보낼 수 없습니다. (user_id=%d)",
                user_id,
            )
            return

        try:
            await self._notification_provider.send_notification(user_id, message)

            async with self._pool.acquire() as conn:
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
                    "알림 발송 실패, 재시도 (%d/3)",
                    retry + 1,
                    extra={"user_id": user_id, "error": str(e)},
                )
                await asyncio.sleep(2**retry)
                await self._send_scheduled_dm(user_id, schedule_id, message, retry + 1)
            else:
                log.error(
                    "알림 발송 최대 재시도 초과",
                    extra={
                        "user_id": user_id,
                        "schedule_id": schedule_id,
                        "error": str(e),
                    },
                )

    async def restore_schedules(self) -> None:
        """DB에서 아직 발송되지 않은 미래의 일정을 불러와 스케줄러에 재등록합니다."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, message, trigger_at
                FROM schedules
                WHERE sent = FALSE AND trigger_at > NOW()
                """
            )

        for row in rows:
            sid_str = str(row["id"])
            self._scheduler.add_job(
                self._send_scheduled_dm,
                "date",
                run_date=row["trigger_at"],
                args=[row["user_id"], sid_str, row["message"]],
                id=sid_str,
                replace_existing=True,
            )
        log.info("미발송 스케줄 복구 완료", extra={"count": len(rows)})
