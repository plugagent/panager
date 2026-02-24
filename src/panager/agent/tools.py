from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from panager.services.google import GoogleService
    from panager.services.memory import MemoryService
    from panager.services.scheduler import SchedulerService

log = logging.getLogger(__name__)


# --- Action Enums & Base Models ---


class MemoryAction(str, Enum):
    SAVE = "save"
    SEARCH = "search"


class MemoryToolInput(BaseModel):
    action: MemoryAction
    content: str | None = None
    query: str | None = None
    limit: int = 5

    @model_validator(mode="after")
    def validate_action_fields(self) -> MemoryToolInput:
        if self.action == MemoryAction.SAVE and not self.content:
            raise ValueError("action='save' requires 'content'")
        if self.action == MemoryAction.SEARCH and not self.query:
            raise ValueError("action='search' requires 'query'")
        return self


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


class TaskAction(str, Enum):
    LIST = "list"
    CREATE = "create"
    UPDATE_STATUS = "update_status"
    DELETE = "delete"


class TaskToolInput(BaseModel):
    action: TaskAction
    task_id: str | None = None
    title: str | None = None
    status: str | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> TaskToolInput:
        if self.action == TaskAction.CREATE and not self.title:
            raise ValueError("action='create' requires 'title'")
        if self.action == TaskAction.UPDATE_STATUS and not self.task_id:
            raise ValueError("action='update_status' requires 'task_id'")
        if self.action == TaskAction.DELETE and not self.task_id:
            raise ValueError("action='delete' requires 'task_id'")
        return self


class CalendarAction(str, Enum):
    LIST = "list"
    CREATE = "create"
    DELETE = "delete"


class CalendarToolInput(BaseModel):
    action: CalendarAction
    event_id: str | None = None
    calendar_id: str = "primary"
    title: str | None = None
    start_at: str | None = Field(
        None,
        description="ISO 8601 형식. 시간 미지정 시 오전 9시(09:00:00)를 기본값으로 사용하세요. 예: 2026-02-23T09:00:00+09:00",
    )
    end_at: str | None = Field(
        None,
        description="ISO 8601 형식. 시간 미지정 시 오전 10시(10:00:00) 등을 기본값으로 사용하거나 시작 시간으로부터 적절히 설정하세요.",
    )
    days_ahead: int = 7

    @model_validator(mode="after")
    def validate_action_fields(self) -> CalendarToolInput:
        if self.action == CalendarAction.CREATE:
            if not self.title:
                raise ValueError("action='create' requires 'title'")
            if not self.start_at:
                raise ValueError("action='create' requires 'start_at'")
            if not self.end_at:
                raise ValueError("action='create' requires 'end_at'")
        if self.action == CalendarAction.DELETE and not self.event_id:
            raise ValueError(f"action='{self.action.value}' requires 'event_id'")
        return self


# --- Memory Tools ---


def make_manage_user_memory(user_id: int, memory_service: MemoryService) -> BaseTool:
    @tool(args_schema=MemoryToolInput)
    async def manage_user_memory(
        action: MemoryAction,
        content: str | None = None,
        query: str | None = None,
        limit: int = 5,
    ) -> str:
        """사용자의 중요한 정보를 저장하거나 과거 메모리를 검색합니다.

        - action='save': content에 내용을 입력하여 저장합니다.
        - action='search': query에 검색어를 입력하여 관련 메모리를 찾습니다.
        """
        if action == MemoryAction.SAVE:
            # MemoryToolInput validation ensures content is present for SAVE
            await memory_service.save_memory(user_id, content)  # type: ignore
            return json.dumps(
                {
                    "status": "success",
                    "action": "save",
                    "content_preview": content[:50],
                },  # type: ignore
                ensure_ascii=False,
            )
        elif action == MemoryAction.SEARCH:
            # MemoryToolInput validation ensures query is present for SEARCH
            results = await memory_service.search_memories(user_id, query, limit)  # type: ignore
            return json.dumps(
                {"status": "success", "action": "search", "results": results},
                ensure_ascii=False,
            )
        raise ValueError(f"지원하지 않는 액션입니다: {action}")

    return manage_user_memory


# --- Scheduler Tools ---


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


# --- Google Tasks Tools ---


def make_manage_google_tasks(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=TaskToolInput)
    async def manage_google_tasks(
        action: TaskAction,
        task_id: str | None = None,
        title: str | None = None,
        status: str | None = None,
    ) -> str:
        """Google Tasks의 할 일을 관리(조회, 추가, 상태 수정, 삭제)합니다.

        - action='list': 할 일 목록을 조회합니다.
        - action='create': title이 필수입니다. 새 할 일을 추가합니다.
        - action='update_status': task_id와 status('needsAction' 또는 'completed')가 필수입니다.
        - action='delete': task_id가 필수입니다. 할 일을 삭제합니다.
        """
        service = await google_service.get_tasks_service(user_id)

        if action == TaskAction.LIST:
            items = []
            next_page_token = None
            while True:
                result = await asyncio.to_thread(
                    service.tasks()
                    .list(tasklist="@default", pageToken=next_page_token)
                    .execute
                )
                items.extend(result.get("items", []))
                next_page_token = result.get("nextPageToken")
                if not next_page_token:
                    break
            return json.dumps({"status": "success", "tasks": items}, ensure_ascii=False)

        elif action == TaskAction.CREATE:
            body = {"title": title}
            result = await asyncio.to_thread(
                service.tasks().insert(tasklist="@default", body=body).execute
            )
            return json.dumps({"status": "success", "task": result}, ensure_ascii=False)

        elif action == TaskAction.UPDATE_STATUS:
            body = {"status": status}
            result = await asyncio.to_thread(
                service.tasks()
                .patch(tasklist="@default", task=task_id, body=body)
                .execute
            )
            return json.dumps({"status": "success", "task": result}, ensure_ascii=False)

        elif action == TaskAction.DELETE:
            await asyncio.to_thread(
                service.tasks().delete(tasklist="@default", task=task_id).execute
            )
            return json.dumps(
                {"status": "success", "task_id": task_id}, ensure_ascii=False
            )

        raise ValueError(f"지원하지 않는 액션입니다: {action}")

    return manage_google_tasks


# --- Google Calendar Tools ---


def make_manage_google_calendar(
    user_id: int, google_service: GoogleService
) -> BaseTool:
    @tool(args_schema=CalendarToolInput)
    async def manage_google_calendar(
        action: CalendarAction,
        event_id: str | None = None,
        calendar_id: str = "primary",
        title: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        days_ahead: int = 7,
    ) -> str:
        """Google Calendar의 이벤트를 관리(조회, 추가, 삭제)합니다.

        - action='list': 앞으로 N일(days_ahead) 이내의 모든 이벤트를 조회합니다.
        - action='create': title, start_at, end_at이 필수입니다. 새 이벤트를 추가합니다.
        - action='delete': event_id가 필수입니다. 이벤트를 삭제합니다.
        """
        service = await google_service.get_calendar_service(user_id)

        if action == CalendarAction.LIST:
            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=days_ahead)).isoformat()

            calendars_result = (
                await asyncio.to_thread(service.calendarList().list().execute) or {}
            )
            calendars = calendars_result.get("items", [])
            all_events: list[dict[str, Any]] = []

            for cal in calendars:
                cal_id = cal["id"]
                next_page_token = None
                while True:
                    result = (
                        await asyncio.to_thread(
                            service.events()
                            .list(
                                calendarId=cal_id,
                                timeMin=time_min,
                                timeMax=time_max,
                                singleEvents=True,
                                orderBy="startTime",
                                pageToken=next_page_token,
                            )
                            .execute
                        )
                        or {}
                    )
                    items = result.get("items", [])
                    for item in items:
                        item["calendar_id"] = cal_id
                    all_events.extend(items)

                    next_page_token = result.get("nextPageToken")
                    if not next_page_token:
                        break

            return json.dumps(
                {"status": "success", "events": all_events}, ensure_ascii=False
            )

        elif action == CalendarAction.CREATE:
            body: dict = {
                "summary": title,
                "start": {"dateTime": start_at},
                "end": {"dateTime": end_at},
            }
            created = (
                await asyncio.to_thread(
                    service.events().insert(calendarId=calendar_id, body=body).execute
                )
                or {}
            )
            return json.dumps(
                {"status": "success", "event": created}, ensure_ascii=False
            )

        elif action == CalendarAction.DELETE:
            await asyncio.to_thread(
                service.events()
                .delete(calendarId=calendar_id, eventId=event_id)
                .execute
            )
            return json.dumps(
                {"status": "success", "event_id": event_id}, ensure_ascii=False
            )

        raise ValueError(f"지원하지 않는 액션입니다: {action}")

    return manage_google_calendar
