from __future__ import annotations

from datetime import datetime, timezone, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langchain_core.tools import tool
from pydantic import BaseModel

from panager.google.auth import refresh_access_token
from panager.google.repository import get_tokens, update_access_token


class GoogleAuthRequired(Exception):
    """Google 계정 미연동 또는 scope 부족 시 발생하는 예외."""


async def _get_valid_credentials(user_id: int) -> Credentials:
    tokens = await get_tokens(user_id)
    if not tokens:
        raise GoogleAuthRequired("Google 계정이 연동되지 않았습니다.")

    if tokens.expires_at <= datetime.now(timezone.utc):
        new_token, new_expires = await refresh_access_token(tokens.refresh_token)
        await update_access_token(user_id, new_token, new_expires)
        tokens.access_token = new_token

    return Credentials(token=tokens.access_token)


def _execute(request):
    """googleapiclient 요청을 실행하고 403은 GoogleAuthRequired로 변환합니다."""
    try:
        return request.execute()
    except HttpError as exc:
        if exc.status_code == 403:
            raise GoogleAuthRequired("Google 권한이 부족합니다. 재연동이 필요합니다.")
        raise


def _build_service(creds: Credentials):
    return build("tasks", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Tool factories – user_id is captured via closure, not exposed to the LLM
# ---------------------------------------------------------------------------


class TaskListInput(BaseModel):
    pass


class TaskCreateInput(BaseModel):
    title: str
    due_at: str | None = None


class TaskCompleteInput(BaseModel):
    task_id: str


def make_task_list(user_id: int):
    @tool(args_schema=TaskListInput)
    async def task_list() -> str:
        """Google Tasks의 할 일 목록을 조회합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_service(creds)
        result = _execute(service.tasks().list(tasklist="@default"))
        items = result.get("items", [])
        if not items:
            return "할 일이 없습니다."
        return "\n".join(
            f"- [{item['id']}] {item['title']}"
            for item in items
            if item.get("status") == "needsAction"
        )

    return task_list


def make_task_create(user_id: int):
    @tool(args_schema=TaskCreateInput)
    async def task_create(title: str, due_at: str | None = None) -> str:
        """Google Tasks에 새 할 일을 추가합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_service(creds)
        body: dict = {"title": title}
        if due_at:
            body["due"] = due_at
        _execute(service.tasks().insert(tasklist="@default", body=body))
        return f"할 일이 추가되었습니다: {title}"

    return task_create


def make_task_complete(user_id: int):
    @tool(args_schema=TaskCompleteInput)
    async def task_complete(task_id: str) -> str:
        """Google Tasks의 할 일을 완료 처리합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_service(creds)
        _execute(
            service.tasks().patch(
                tasklist="@default", task=task_id, body={"status": "completed"}
            )
        )
        return f"할 일이 완료 처리되었습니다: {task_id}"

    return task_complete


# ---------------------------------------------------------------------------
# Calendar service helper
# ---------------------------------------------------------------------------


def _build_calendar_service(creds: Credentials):
    return build("calendar", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Calendar tool input schemas
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Calendar tool factories – user_id는 클로저로 캡처
# ---------------------------------------------------------------------------


def make_event_list(user_id: int):
    @tool(args_schema=EventListInput)
    async def event_list(days_ahead: int = 7) -> str:
        """Google Calendar에서 앞으로 N일 이내의 이벤트를 모든 캘린더에서 조회합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_calendar_service(creds)

        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days_ahead)).isoformat()

        calendars = _execute(service.calendarList().list()).get("items", [])
        events: list[str] = []

        for cal in calendars:
            cal_id = cal["id"]
            result = _execute(
                service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
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


def make_event_create(user_id: int):
    @tool(args_schema=EventCreateInput)
    async def event_create(
        title: str,
        start_at: str,
        end_at: str,
        calendar_id: str = "primary",
        description: str | None = None,
    ) -> str:
        """Google Calendar에 새 이벤트를 추가합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_calendar_service(creds)

        body: dict = {
            "summary": title,
            "start": {"dateTime": start_at},
            "end": {"dateTime": end_at},
        }
        if description:
            body["description"] = description

        created = _execute(service.events().insert(calendarId=calendar_id, body=body))
        return f"이벤트가 추가되었습니다: {created.get('summary')} (id={created.get('id')})"

    return event_create


def make_event_update(user_id: int):
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
        creds = await _get_valid_credentials(user_id)
        service = _build_calendar_service(creds)

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

        _execute(
            service.events().patch(
                calendarId=calendar_id, eventId=event_id, body=patch_body
            )
        )
        return f"이벤트가 수정되었습니다: {event_id}"

    return event_update


def make_event_delete(user_id: int):
    @tool(args_schema=EventDeleteInput)
    async def event_delete(event_id: str, calendar_id: str = "primary") -> str:
        """Google Calendar 이벤트를 삭제합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_calendar_service(creds)
        _execute(service.events().delete(calendarId=calendar_id, eventId=event_id))
        return f"이벤트가 삭제되었습니다: {event_id}"

    return event_delete


# ---------------------------------------------------------------------------
# Standalone tool objects kept for backward compatibility (e.g. slash commands)
# These still require user_id as an argument.
# ---------------------------------------------------------------------------


class _TaskListInputLegacy(BaseModel):
    user_id: int


class _TaskCreateInputLegacy(BaseModel):
    title: str
    user_id: int
    due_at: str | None = None


class _TaskCompleteInputLegacy(BaseModel):
    task_id: str
    user_id: int


@tool(args_schema=_TaskListInputLegacy)
async def task_list(user_id: int) -> str:
    """Google Tasks의 할 일 목록을 조회합니다."""
    creds = await _get_valid_credentials(user_id)
    service = _build_service(creds)
    result = _execute(service.tasks().list(tasklist="@default"))
    items = result.get("items", [])
    if not items:
        return "할 일이 없습니다."
    return "\n".join(
        f"- [{item['id']}] {item['title']}"
        for item in items
        if item.get("status") == "needsAction"
    )


@tool(args_schema=_TaskCreateInputLegacy)
async def task_create(title: str, user_id: int, due_at: str | None = None) -> str:
    """Google Tasks에 새 할 일을 추가합니다."""
    creds = await _get_valid_credentials(user_id)
    service = _build_service(creds)
    body: dict = {"title": title}
    if due_at:
        body["due"] = due_at
    _execute(service.tasks().insert(tasklist="@default", body=body))
    return f"할 일이 추가되었습니다: {title}"


@tool(args_schema=_TaskCompleteInputLegacy)
async def task_complete(task_id: str, user_id: int) -> str:
    """Google Tasks의 할 일을 완료 처리합니다."""
    creds = await _get_valid_credentials(user_id)
    service = _build_service(creds)
    _execute(
        service.tasks().patch(
            tasklist="@default", task=task_id, body={"status": "completed"}
        )
    )
    return f"할 일이 완료 처리되었습니다: {task_id}"
