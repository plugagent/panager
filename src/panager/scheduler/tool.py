from __future__ import annotations

from datetime import datetime
from uuid import UUID

from langchain_core.tools import tool
from pydantic import BaseModel

from panager.db.connection import get_pool
from panager.scheduler.runner import get_scheduler, send_scheduled_dm


class ScheduleCreateInput(BaseModel):
    message: str
    trigger_at: str  # ISO 8601 형식
    user_id: int


class ScheduleCancelInput(BaseModel):
    schedule_id: str
    user_id: int


@tool(args_schema=ScheduleCreateInput)
async def schedule_create(message: str, trigger_at: str, user_id: int) -> str:
    """지정한 시간에 사용자에게 DM 알림을 예약합니다."""
    trigger_dt = datetime.fromisoformat(trigger_at)
    pool = get_pool()
    async with pool.acquire() as conn:
        schedule_id = await conn.fetchval(
            """
            INSERT INTO schedules (user_id, message, trigger_at)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            user_id,
            message,
            trigger_dt,
        )

    scheduler = get_scheduler()
    scheduler.add_job(
        send_scheduled_dm,
        "date",
        run_date=trigger_dt,
        args=[None, user_id, str(schedule_id), message],
        id=str(schedule_id),
        replace_existing=True,
    )
    return f"알림이 예약되었습니다: {trigger_at}에 '{message}'"


@tool(args_schema=ScheduleCancelInput)
async def schedule_cancel(schedule_id: str, user_id: int) -> str:
    """예약된 알림을 취소합니다."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM schedules WHERE id = $1 AND user_id = $2",
            UUID(schedule_id),
            user_id,
        )
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(schedule_id)
    except Exception:
        pass
    return f"알림이 취소되었습니다: {schedule_id}"
