from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from panager.services.google import GoogleService
    from panager.services.memory import MemoryService
    from panager.services.scheduler import SchedulerService

log = logging.getLogger(__name__)


# --- Memory Tools ---


class MemorySaveInput(BaseModel):
    content: str


class MemorySearchInput(BaseModel):
    query: str
    limit: int = 5


def make_memory_save(user_id: int, memory_service: MemoryService) -> BaseTool:
    @tool(args_schema=MemorySaveInput)
    async def memory_save(content: str) -> str:
        """중요한 내용을 장기 메모리에 저장합니다."""
        await memory_service.save_memory(user_id, content)
        return json.dumps(
            {"status": "success", "content_preview": content[:50]}, ensure_ascii=False
        )

    return memory_save


def make_memory_search(user_id: int, memory_service: MemoryService) -> BaseTool:
    @tool(args_schema=MemorySearchInput)
    async def memory_search(query: str, limit: int = 5) -> str:
        """사용자의 과거 대화/패턴에서 관련 내용을 검색합니다."""
        results = await memory_service.search_memories(user_id, query, limit)
        return json.dumps({"status": "success", "results": results}, ensure_ascii=False)

    return memory_search


# --- Scheduler Tools ---


class ScheduleCreateInput(BaseModel):
    command: str  # 알림 메시지 또는 실행할 명령
    trigger_at: str = Field(
        ...,
        description="ISO 8601 형식 (반드시 초(Second) 단위와 타임존을 포함해야 함). 예: 2026-02-23T14:30:15+09:00",
    )
    type: str = "notification"  # 'notification' or 'command'
    payload: dict | None = None


class ScheduleCancelInput(BaseModel):
    schedule_id: str


def make_schedule_create(user_id: int, scheduler_service: SchedulerService) -> BaseTool:
    @tool(args_schema=ScheduleCreateInput)
    async def schedule_create(
        command: str,
        trigger_at: str,
        type: str = "notification",
        payload: dict | None = None,
    ) -> str:
        """지정한 시간에 사용자에게 DM 알림을 보내거나 명령(command)을 실행하도록 예약합니다.
        단순 알림은 type='notification'을, 특정 명령 실행은 type='command'를 사용하세요.
        command 인자에는 알림 내용 또는 실행할 명령 텍스트를 입력합니다.
        """
        trigger_dt = datetime.fromisoformat(trigger_at)
        schedule_id = await scheduler_service.add_schedule(
            user_id, command, trigger_dt, type, payload
        )
        return json.dumps(
            {
                "status": "success",
                "schedule_id": str(schedule_id),
                "trigger_at": trigger_at,
                "type": type,
            },
            ensure_ascii=False,
        )

    return schedule_create


def make_schedule_cancel(user_id: int, scheduler_service: SchedulerService) -> BaseTool:
    @tool(args_schema=ScheduleCancelInput)
    async def schedule_cancel(schedule_id: str) -> str:
        """예약된 알림을 취소합니다."""
        success = await scheduler_service.cancel_schedule(user_id, schedule_id)
        return json.dumps(
            {"status": "success" if success else "failed", "schedule_id": schedule_id},
            ensure_ascii=False,
        )

    return schedule_cancel


# --- Google Tasks Tools ---


class TaskListInput(BaseModel):
    pass


class TaskCreateInput(BaseModel):
    title: str
    due_at: str | None = None
    notes: str | None = None
    parent_id: str | None = None


class TaskUpdateInput(BaseModel):
    task_id: str
    title: str | None = None
    notes: str | None = None
    status: str | None = None  # 'needsAction' or 'completed'
    due_at: str | None = None
    starred: bool | None = None


class TaskDeleteInput(BaseModel):
    task_id: str


def make_task_list(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=TaskListInput)
    async def task_list() -> str:
        """Google Tasks의 할 일 목록을 조회합니다."""
        service = await google_service.get_tasks_service(user_id)
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

    return task_list


def make_task_create(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=TaskCreateInput)
    async def task_create(
        title: str,
        due_at: str | None = None,
        notes: str | None = None,
        parent_id: str | None = None,
    ) -> str:
        """Google Tasks에 새 할 일을 추가합니다."""
        service = await google_service.get_tasks_service(user_id)
        body: dict = {"title": title}
        if due_at:
            body["due"] = due_at
        if notes:
            body["notes"] = notes

        result = await asyncio.to_thread(
            service.tasks()
            .insert(tasklist="@default", body=body, parent=parent_id)
            .execute
        )
        return json.dumps({"status": "success", "task": result}, ensure_ascii=False)

    return task_create


def make_task_update(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=TaskUpdateInput)
    async def task_update(
        task_id: str,
        title: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        due_at: str | None = None,
        starred: bool | None = None,
    ) -> str:
        """Google Tasks의 할 일을 수정합니다."""
        service = await google_service.get_tasks_service(user_id)
        body: dict = {}
        if title is not None:
            body["title"] = title
        if notes is not None:
            body["notes"] = notes
        if status is not None:
            body["status"] = status
        if due_at is not None:
            body["due"] = due_at

        # (검색 기반 정보) starred 필드는 공식 문서에는 없지만,
        # 일부 내부 리소스나 실험적 필드로 작동하는지 시도
        if starred is not None:
            # star 필드가 유효하지 않을 경우 HttpError가 발생할 수 있으므로
            # 여기서는 body에 포함하되 실패 시 무시하도록 처리 가능
            body["starred"] = starred

        result = await asyncio.to_thread(
            service.tasks().patch(tasklist="@default", task=task_id, body=body).execute
        )
        return json.dumps({"status": "success", "task": result}, ensure_ascii=False)

    return task_update


def make_task_delete(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=TaskDeleteInput)
    async def task_delete(task_id: str) -> str:
        """Google Tasks의 할 일을 삭제합니다."""
        service = await google_service.get_tasks_service(user_id)
        await asyncio.to_thread(
            service.tasks().delete(tasklist="@default", task=task_id).execute
        )
        return json.dumps({"status": "success", "task_id": task_id}, ensure_ascii=False)

    return task_delete


# --- Google Calendar Tools ---


class EventListInput(BaseModel):
    days_ahead: int = 7


class EventCreateInput(BaseModel):
    title: str
    start_at: str  # ISO 8601 (예: "2026-02-21T10:00:00+09:00")
    end_at: str  # ISO 8601
    calendar_id: str = "primary"
    description: str | None = None


class EventUpdateInput(BaseModel):
    event_id: str
    calendar_id: str = "primary"
    title: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    description: str | None = None


class EventDeleteInput(BaseModel):
    event_id: str
    calendar_id: str = "primary"


def make_event_list(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=EventListInput)
    async def event_list(days_ahead: int = 7) -> str:
        """Google Calendar에서 앞으로 N일 이내의 이벤트를 모든 캘린더에서 조회합니다."""
        service = await google_service.get_calendar_service(user_id)

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

    return event_list


def make_event_create(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=EventCreateInput)
    async def event_create(
        title: str,
        start_at: str,
        end_at: str,
        calendar_id: str = "primary",
        description: str | None = None,
    ) -> str:
        """Google Calendar에 새 이벤트를 추가합니다."""
        service = await google_service.get_calendar_service(user_id)

        body: dict = {
            "summary": title,
            "start": {"dateTime": start_at},
            "end": {"dateTime": end_at},
        }
        if description:
            body["description"] = description

        created = (
            await asyncio.to_thread(
                service.events().insert(calendarId=calendar_id, body=body).execute
            )
            or {}
        )
        return json.dumps({"status": "success", "event": created}, ensure_ascii=False)

    return event_create


def make_event_update(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=EventUpdateInput)
    async def event_update(
        event_id: str,
        calendar_id: str = "primary",
        title: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        description: str | None = None,
    ) -> str:
        """Google Calendar 이벤트를 수정합니다. 변경할 필드만 전달하세요."""
        service = await google_service.get_calendar_service(user_id)

        patch_body: dict = {}
        if title is not None:
            patch_body["summary"] = title
        if start_at is not None:
            patch_body["start"] = {"dateTime": start_at}
        if end_at is not None:
            patch_body["end"] = {"dateTime": end_at}
        if description is not None:
            patch_body["description"] = description

        if not patch_body:
            return json.dumps(
                {"status": "error", "message": "수정할 필드를 하나 이상 지정해주세요."},
                ensure_ascii=False,
            )

        result = await asyncio.to_thread(
            service.events()
            .patch(calendarId=calendar_id, eventId=event_id, body=patch_body)
            .execute
        )
        return json.dumps({"status": "success", "event": result}, ensure_ascii=False)

    return event_update


def make_event_delete(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=EventDeleteInput)
    async def event_delete(event_id: str, calendar_id: str = "primary") -> str:
        """Google Calendar 이벤트를 삭제합니다."""
        service = await google_service.get_calendar_service(user_id)
        await asyncio.to_thread(
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute
        )
        return json.dumps(
            {"status": "success", "event_id": event_id}, ensure_ascii=False
        )

    return event_delete
