from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from langchain_core.tools import tool
from pydantic import BaseModel

if TYPE_CHECKING:
    from panager.services.scheduler import SchedulerService


# ---------------------------------------------------------------------------
# Tool factories – user_id is captured via closure, not exposed to the LLM
# ---------------------------------------------------------------------------


class ScheduleCreateInput(BaseModel):
    message: str
    trigger_at: str  # ISO 8601 형식


class ScheduleCancelInput(BaseModel):
    schedule_id: str


def make_schedule_create(user_id: int, scheduler_service: SchedulerService):
    @tool(args_schema=ScheduleCreateInput)
    async def schedule_create(message: str, trigger_at: str) -> str:
        """지정한 시간에 사용자에게 DM 알림을 예약합니다."""
        trigger_dt = datetime.fromisoformat(trigger_at)
        await scheduler_service.add_schedule(user_id, message, trigger_dt)
        return f"알림이 예약되었습니다: {trigger_at}에 '{message}'"

    return schedule_create


def make_schedule_cancel(user_id: int, scheduler_service: SchedulerService):
    @tool(args_schema=ScheduleCancelInput)
    async def schedule_cancel(schedule_id: str) -> str:
        """예약된 알림을 취소합니다."""
        success = await scheduler_service.cancel_schedule(user_id, schedule_id)
        if success:
            return f"알림이 취소되었습니다: {schedule_id}"
        return (
            f"알림 취소에 실패했습니다 (이미 발송되었거나 권한이 없음): {schedule_id}"
        )

    return schedule_cancel
