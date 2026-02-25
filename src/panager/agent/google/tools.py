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

log = logging.getLogger(__name__)


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
