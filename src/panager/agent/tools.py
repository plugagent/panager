from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from langchain_core.tools import tool
from pydantic import BaseModel

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
        return f"메모리에 저장했습니다: {content[:50]}"

    return memory_save


def make_memory_search(user_id: int, memory_service: MemoryService) -> BaseTool:
    @tool(args_schema=MemorySearchInput)
    async def memory_search(query: str, limit: int = 5) -> str:
        """사용자의 과거 대화/패턴에서 관련 내용을 검색합니다."""
        results = await memory_service.search_memories(user_id, query, limit)
        if not results:
            return "관련 메모리가 없습니다."
        return "\n".join(f"- {r}" for r in results)

    return memory_search


# --- Scheduler Tools ---


class ScheduleCreateInput(BaseModel):
    message: str
    trigger_at: str  # ISO 8601 형식


class ScheduleCancelInput(BaseModel):
    schedule_id: str


def make_schedule_create(user_id: int, scheduler_service: SchedulerService) -> BaseTool:
    @tool(args_schema=ScheduleCreateInput)
    async def schedule_create(message: str, trigger_at: str) -> str:
        """지정한 시간에 사용자에게 DM 알림을 예약합니다."""
        trigger_dt = datetime.fromisoformat(trigger_at)
        await scheduler_service.add_schedule(user_id, message, trigger_dt)
        return f"알림이 예약되었습니다: {trigger_at}에 '{message}'"

    return schedule_create


def make_schedule_cancel(user_id: int, scheduler_service: SchedulerService) -> BaseTool:
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


# --- Google Tasks Tools ---


class TaskListInput(BaseModel):
    pass


class TaskCreateInput(BaseModel):
    title: str
    due_at: str | None = None


class TaskCompleteInput(BaseModel):
    task_id: str


def make_task_list(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=TaskListInput)
    async def task_list() -> str:
        """Google Tasks의 할 일 목록을 조회합니다."""
        service = await google_service.get_tasks_service(user_id)
        result = await asyncio.to_thread(
            service.tasks().list(tasklist="@default").execute
        )
        items = result.get("items", [])
        if not items:
            return "할 일이 없습니다."
        pending = [
            f"- [{item['id']}] {item['title']}"
            for item in items
            if item.get("status") == "needsAction"
        ]
        if not pending:
            return "완료되지 않은 할 일이 없습니다."
        return "\n".join(pending)

    return task_list


def make_task_create(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=TaskCreateInput)
    async def task_create(title: str, due_at: str | None = None) -> str:
        """Google Tasks에 새 할 일을 추가합니다."""
        service = await google_service.get_tasks_service(user_id)
        body: dict = {"title": title}
        if due_at:
            body["due"] = due_at
        await asyncio.to_thread(
            service.tasks().insert(tasklist="@default", body=body).execute
        )
        return f"할 일이 추가되었습니다: {title}"

    return task_create


def make_task_complete(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=TaskCompleteInput)
    async def task_complete(task_id: str) -> str:
        """Google Tasks의 할 일을 완료 처리합니다."""
        service = await google_service.get_tasks_service(user_id)
        await asyncio.to_thread(
            service.tasks()
            .patch(tasklist="@default", task=task_id, body={"status": "completed"})
            .execute
        )
        return f"할 일이 완료 처리되었습니다: {task_id}"

    return task_complete


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
        events: list[str] = []

        for cal in calendars:
            cal_id = cal["id"]
            result = (
                await asyncio.to_thread(
                    service.events()
                    .list(
                        calendarId=cal_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute
                )
                or {}
            )
            for evt in result.get("items", []):
                start = evt.get("start", {}).get("dateTime") or evt.get(
                    "start", {}
                ).get("date", "")
                title = evt.get("summary", "(제목 없음)")
                evt_id = evt.get("id", "")
                events.append(f"- [{start}] {title} (id={evt_id}, cal={cal_id})")

        if not events:
            return f"앞으로 {days_ahead}일 이내 일정이 없습니다."
        return "\n".join(events)

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
        return f"이벤트가 추가되었습니다: {created.get('summary')} (id={created.get('id')})"

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
            return "수정할 필드를 하나 이상 지정해주세요."

        await asyncio.to_thread(
            service.events()
            .patch(calendarId=calendar_id, eventId=event_id, body=patch_body)
            .execute
        )
        return f"이벤트가 수정되었습니다: {event_id}"

    return event_update


def make_event_delete(user_id: int, google_service: GoogleService) -> BaseTool:
    @tool(args_schema=EventDeleteInput)
    async def event_delete(event_id: str, calendar_id: str = "primary") -> str:
        """Google Calendar 이벤트를 삭제합니다."""
        service = await google_service.get_calendar_service(user_id)
        await asyncio.to_thread(
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute
        )
        return f"이벤트가 삭제되었습니다: {event_id}"

    return event_delete
