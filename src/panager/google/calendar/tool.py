from __future__ import annotations

from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import tool
from pydantic import BaseModel

from panager.google.credentials import _execute, _get_valid_credentials


def _build_service(creds: Credentials):
    return build("calendar", "v3", credentials=creds)


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


def make_event_list(user_id: int):
    @tool(args_schema=EventListInput)
    async def event_list(days_ahead: int = 7) -> str:
        """Google Calendar에서 앞으로 N일 이내의 이벤트를 모든 캘린더에서 조회합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_service(creds)

        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days_ahead)).isoformat()

        calendars_result = await _execute(service.calendarList().list()) or {}
        calendars = calendars_result.get("items", [])
        events: list[str] = []

        for cal in calendars:
            cal_id = cal["id"]
            result = (
                await _execute(
                    service.events().list(
                        calendarId=cal_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        singleEvents=True,
                        orderBy="startTime",
                    )
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
        service = _build_service(creds)

        body: dict = {
            "summary": title,
            "start": {"dateTime": start_at},
            "end": {"dateTime": end_at},
        }
        if description:
            body["description"] = description

        created = (
            await _execute(service.events().insert(calendarId=calendar_id, body=body))
            or {}
        )
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
        service = _build_service(creds)

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

        await _execute(
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
        service = _build_service(creds)
        await _execute(
            service.events().delete(calendarId=calendar_id, eventId=event_id)
        )
        return f"이벤트가 삭제되었습니다: {event_id}"

    return event_delete
