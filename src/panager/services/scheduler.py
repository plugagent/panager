from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Protocol, TYPE_CHECKING, Any, Dict
from uuid import UUID

if TYPE_CHECKING:
    import asyncpg

log = logging.getLogger(__name__)


class NotificationProvider(Protocol):
    """알림 및 작업을 트리거하기 위한 인터페이스."""

    async def send_notification(self, user_id: int, message: str) -> None: ...

    async def trigger_task(
        self, user_id: int, command: str, payload: Dict[str, Any] | None = None
    ) -> None: ...


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
        self,
        user_id: int,
        message: str,
        trigger_at: datetime,
        type_: str = "notification",
        payload: Dict[str, Any] | None = None,
    ) -> UUID:
        """새로운 알림 일정을 추가하고 스케줄러에 등록합니다."""
        import json

        async with self._pool.acquire() as conn:
            schedule_id = await conn.fetchval(
                """
                INSERT INTO schedules (user_id, message, trigger_at, type, payload)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                user_id,
                message,
                trigger_at,
                type_,
                json.dumps(payload) if payload else None,
            )

        sid_str = str(schedule_id)
        self._scheduler.add_job(
            self._execute_schedule,
            "date",
            run_date=trigger_at,
            args=[user_id, sid_str, message, type_, payload],
            id=sid_str,
            replace_existing=True,
        )
        return UUID(sid_str)

    async def cancel_schedule(self, user_id: int, schedule_id: str) -> bool:
        """예약된 알림 일정을 취소합니다."""
        try:
            sid = UUID(schedule_id)
        except ValueError:
            return False

        async with self._pool.acquire() as conn:
            # user_id를 확인하여 본인의 일정만 삭제 가능하도록 함
            result = await conn.execute(
                "DELETE FROM schedules WHERE id = $1 AND user_id = $2",
                sid,
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

    async def _execute_schedule(
        self,
        user_id: int,
        schedule_id: str,
        message: str,
        type_: str = "notification",
        payload: Dict[str, Any] | None = None,
        retry: int = 0,
    ) -> None:
        """스케줄러에 의해 호출되어 실제 알림 또는 작업을 실행합니다."""
        if self._notification_provider is None:
            log.error(
                "알림 제공자가 설정되지 않아 알림을 보낼 수 없습니다. (user_id=%d)",
                user_id,
            )
            return

        try:
            if type_ == "command":
                await self._notification_provider.trigger_task(
                    user_id, message, payload
                )
            else:
                await self._notification_provider.send_notification(user_id, message)

            async with self._pool.acquire() as conn:
                await conn.execute(
                    "UPDATE schedules SET sent = TRUE WHERE id = $1",
                    UUID(schedule_id),
                )
            log.info(
                "스케줄 실행 완료",
                extra={
                    "user_id": user_id,
                    "schedule_id": schedule_id,
                    "type": type_,
                },
            )
        except Exception as e:
            if retry < 3:
                log.warning(
                    "스케줄 실행 실패, 재시도 (%d/3)",
                    retry + 1,
                    extra={"user_id": user_id, "error": str(e)},
                )
                await asyncio.sleep(2**retry)
                await self._execute_schedule(
                    user_id, schedule_id, message, type_, payload, retry + 1
                )
            else:
                log.error(
                    "스케줄 실행 최대 재시도 초과",
                    extra={
                        "user_id": user_id,
                        "schedule_id": schedule_id,
                        "error": str(e),
                    },
                )

    async def restore_schedules(self) -> None:
        """DB에서 아직 발송되지 않은 미래의 일정을 불러와 스케줄러에 재등록합니다."""
        import json

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, message, trigger_at, type, payload
                FROM schedules
                WHERE sent = FALSE AND trigger_at > NOW()
                """
            )

        for row in rows:
            sid_str = str(row["id"])
            payload = json.loads(row["payload"]) if row["payload"] else None
            self._scheduler.add_job(
                self._execute_schedule,
                "date",
                run_date=row["trigger_at"],
                args=[
                    row["user_id"],
                    sid_str,
                    row["message"],
                    row["type"],
                    payload,
                ],
                id=sid_str,
                replace_existing=True,
            )
        log.info("미발송 스케줄 복구 완료", extra={"count": len(rows)})
