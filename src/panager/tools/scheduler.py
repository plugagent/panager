from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from langchain_core.tools import tool
from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

    from panager.services.scheduler import SchedulerService

log = logging.getLogger(__name__)


class ScheduleAction(str, Enum):
    CREATE = "create"
    CANCEL = "cancel"


class ScheduleToolInput(BaseModel):
    action: ScheduleAction
    command: str | None = None
    trigger_at: str | None = Field(
        None,
        description="ISO 8601 형식. 시간 미지정 시 오전 9시(09:00:00)를 기본값으로 사용하세요. 예: 2026-02-23T09:00:00+09:00",
    )
    schedule_id: str | None = None
    type: str = "notification"
    payload: dict | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> ScheduleToolInput:
        if self.action == ScheduleAction.CREATE:
            if not self.command:
                raise ValueError("action='create' requires 'command'")
            if not self.trigger_at:
                raise ValueError("action='create' requires 'trigger_at'")
        if self.action == ScheduleAction.CANCEL and not self.schedule_id:
            raise ValueError("action='cancel' requires 'schedule_id'")
        return self


def make_manage_dm_scheduler(
    user_id: int, scheduler_service: SchedulerService
) -> BaseTool:
    @tool(args_schema=ScheduleToolInput)
    async def manage_dm_scheduler(
        action: ScheduleAction,
        command: str | None = None,
        trigger_at: str | None = None,
        schedule_id: str | None = None,
        type: str = "notification",
        payload: dict | None = None,
    ) -> str:
        """지정한 시간에 사용자에게 DM 알림을 보내거나 명령(command)을 실행하도록 예약 또는 취소합니다.

        - action='create': command, trigger_at이 필수입니다. type은 'notification' 또는 'command'입니다.
        - action='cancel': schedule_id가 필수입니다.
        """
        if action == ScheduleAction.CREATE:
            # ScheduleToolInput validation ensures command and trigger_at are present for CREATE
            trigger_dt = datetime.fromisoformat(trigger_at)  # type: ignore
            new_id = await scheduler_service.add_schedule(
                user_id,
                command,
                trigger_dt,
                type,
                payload,  # type: ignore
            )
            return json.dumps(
                {
                    "status": "success",
                    "action": "create",
                    "schedule_id": str(new_id),
                    "trigger_at": trigger_at,
                    "type": type,
                },
                ensure_ascii=False,
            )
        elif action == ScheduleAction.CANCEL:
            # ScheduleToolInput validation ensures schedule_id is present for CANCEL
            success = await scheduler_service.cancel_schedule(user_id, schedule_id)  # type: ignore
            return json.dumps(
                {
                    "status": "success" if success else "failed",
                    "action": "cancel",
                    "schedule_id": schedule_id,
                },
                ensure_ascii=False,
            )
        raise ValueError(f"지원하지 않는 액션입니다: {action}")

    return manage_dm_scheduler
