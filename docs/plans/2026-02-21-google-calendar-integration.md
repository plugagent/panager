# Google Calendar Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Google Calendar API를 패니저에 통합하여 이벤트 조회·생성·수정·삭제를 LLM 에이전트 툴로 제공한다.

**Architecture:** 기존 `google/tool.py`의 클로저 패턴을 그대로 따라 Calendar tool factory 4개를 추가한다. OAuth scope에 `calendar`를 추가하고, `agent/graph.py`의 `_build_tools()`에 등록한다. DB 변경 없음.

**Tech Stack:** Python 3.13, google-api-python-client, google-auth, langchain-core `@tool`, pytest-asyncio

---

## Task 1: OAuth Scope 확장

**Files:**
- Modify: `src/panager/google/auth.py:12`

**Step 1: `SCOPES`에 calendar 추가**

```python
SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar",
]
```

**Step 2: 기존 테스트 통과 확인**

```bash
uv run pytest tests/google/ -v
```

Expected: 모두 PASS (scope 변경은 테스트에 영향 없음)

**Step 3: Commit**

```bash
git add src/panager/google/auth.py
git commit -m "feat: Google OAuth scope에 calendar 추가"
```

---

## Task 2: Calendar Tool 구현

**Files:**
- Modify: `src/panager/google/tool.py`
- Create: `tests/google/test_calendar_tool.py`

### Step 1: 실패하는 테스트 작성

`tests/google/test_calendar_tool.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta


@pytest.mark.asyncio
async def test_event_list_returns_events():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_calendars = {"items": [{"id": "primary"}]}
    mock_events = {
        "items": [
            {
                "id": "evt1",
                "summary": "팀 회의",
                "start": {"dateTime": "2026-02-21T10:00:00+09:00"},
                "end": {"dateTime": "2026-02-21T11:00:00+09:00"},
            }
        ]
    }
    mock_service.calendarList().list().execute.return_value = mock_calendars
    mock_service.events().list().execute.return_value = mock_events

    with (
        patch("panager.google.tool._get_valid_credentials", new_callable=AsyncMock, return_value=mock_creds),
        patch("panager.google.tool._build_calendar_service", return_value=mock_service),
    ):
        from panager.google.tool import make_event_list
        tool = make_event_list(user_id=123)
        result = await tool.ainvoke({"days_ahead": 7})
        assert "팀 회의" in result
        assert "evt1" in result


@pytest.mark.asyncio
async def test_event_list_no_events():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.calendarList().list().execute.return_value = {"items": [{"id": "primary"}]}
    mock_service.events().list().execute.return_value = {"items": []}

    with (
        patch("panager.google.tool._get_valid_credentials", new_callable=AsyncMock, return_value=mock_creds),
        patch("panager.google.tool._build_calendar_service", return_value=mock_service),
    ):
        from panager.google.tool import make_event_list
        tool = make_event_list(user_id=123)
        result = await tool.ainvoke({"days_ahead": 7})
        assert "없습니다" in result


@pytest.mark.asyncio
async def test_event_create():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.events().insert().execute.return_value = {"id": "new_evt", "summary": "새 이벤트"}

    with (
        patch("panager.google.tool._get_valid_credentials", new_callable=AsyncMock, return_value=mock_creds),
        patch("panager.google.tool._build_calendar_service", return_value=mock_service),
    ):
        from panager.google.tool import make_event_create
        tool = make_event_create(user_id=123)
        result = await tool.ainvoke({
            "title": "새 이벤트",
            "start_at": "2026-02-21T10:00:00+09:00",
            "end_at": "2026-02-21T11:00:00+09:00",
        })
        assert "추가" in result
        assert "새 이벤트" in result


@pytest.mark.asyncio
async def test_event_update():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.events().get().execute.return_value = {
        "id": "evt1",
        "summary": "기존 제목",
        "start": {"dateTime": "2026-02-21T10:00:00+09:00"},
        "end": {"dateTime": "2026-02-21T11:00:00+09:00"},
    }
    mock_service.events().patch().execute.return_value = {}

    with (
        patch("panager.google.tool._get_valid_credentials", new_callable=AsyncMock, return_value=mock_creds),
        patch("panager.google.tool._build_calendar_service", return_value=mock_service),
    ):
        from panager.google.tool import make_event_update
        tool = make_event_update(user_id=123)
        result = await tool.ainvoke({
            "event_id": "evt1",
            "calendar_id": "primary",
            "title": "수정된 제목",
        })
        assert "수정" in result


@pytest.mark.asyncio
async def test_event_delete():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.events().delete().execute.return_value = None

    with (
        patch("panager.google.tool._get_valid_credentials", new_callable=AsyncMock, return_value=mock_creds),
        patch("panager.google.tool._build_calendar_service", return_value=mock_service),
    ):
        from panager.google.tool import make_event_delete
        tool = make_event_delete(user_id=123)
        result = await tool.ainvoke({
            "event_id": "evt1",
            "calendar_id": "primary",
        })
        assert "삭제" in result
```

**Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/google/test_calendar_tool.py -v
```

Expected: FAIL (`make_event_list` 등 import 오류)

**Step 3: Calendar tool factory 구현**

`src/panager/google/tool.py` 하단(legacy 툴 위)에 추가:

```python
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
    end_at: str    # ISO 8601
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

        calendars = service.calendarList().list().execute().get("items", [])
        events: list[str] = []

        for cal in calendars:
            cal_id = cal["id"]
            result = service.events().list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            for evt in result.get("items", []):
                start = evt.get("start", {}).get("dateTime") or evt.get("start", {}).get("date", "")
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

        created = service.events().insert(calendarId=calendar_id, body=body).execute()
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

        service.events().patch(
            calendarId=calendar_id, eventId=event_id, body=patch_body
        ).execute()
        return f"이벤트가 수정되었습니다: {event_id}"

    return event_update


def make_event_delete(user_id: int):
    @tool(args_schema=EventDeleteInput)
    async def event_delete(event_id: str, calendar_id: str = "primary") -> str:
        """Google Calendar 이벤트를 삭제합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_calendar_service(creds)
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return f"이벤트가 삭제되었습니다: {event_id}"

    return event_delete
```

`tool.py` 상단 imports에 `timedelta` 추가 확인:
```python
from datetime import datetime, timezone, timedelta
```

**Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/google/test_calendar_tool.py -v
```

Expected: 5개 PASS

**Step 5: Commit**

```bash
git add src/panager/google/tool.py tests/google/test_calendar_tool.py
git commit -m "feat: Google Calendar 이벤트 조회·생성·수정·삭제 툴 추가"
```

---

## Task 3: Agent graph에 Calendar 툴 등록

**Files:**
- Modify: `src/panager/agent/graph.py`

**Step 1: import 및 `_build_tools()` 수정**

`graph.py`의 import 라인 수정:
```python
from panager.google.tool import (
    make_task_complete,
    make_task_create,
    make_task_list,
    make_event_list,
    make_event_create,
    make_event_update,
    make_event_delete,
)
```

`_build_tools()` 수정:
```python
def _build_tools(user_id: int) -> list:
    return [
        make_memory_save(user_id),
        make_memory_search(user_id),
        make_schedule_create(user_id),
        make_schedule_cancel(user_id),
        make_task_create(user_id),
        make_task_list(user_id),
        make_task_complete(user_id),
        make_event_list(user_id),
        make_event_create(user_id),
        make_event_update(user_id),
        make_event_delete(user_id),
    ]
```

**Step 2: 전체 테스트 통과 확인**

```bash
uv run pytest -v
```

Expected: 모두 PASS

**Step 3: Commit**

```bash
git add src/panager/agent/graph.py
git commit -m "feat: 에이전트 툴 목록에 Calendar 툴 등록"
```

---

## Task 4: Docker 재배포 및 동작 확인

**Step 1: 컨테이너 재빌드 및 재시작**

```bash
docker compose build panager
docker compose up -d panager
```

**Step 2: 로그 확인**

```bash
docker compose logs panager --tail=20
```

Expected: `봇 시작 완료: panager#7221`

**Step 3: 기존 Google 연동 사용자 재인증**

기존 토큰은 `tasks` scope만 있으므로 calendar 요청 시 오류 발생.
재인증 URL로 접속하여 새 scope 동의:
```
http://localhost:8000/auth/google/login?user_id=<Discord_user_id>
```

**Step 4: Discord DM으로 기능 테스트**

```
"이번 주 일정 보여줘"
"내일 오후 3시에 팀 회의 추가해줘"
"방금 추가한 팀 회의 제목을 '주간 싱크'로 바꿔줘"
"주간 싱크 삭제해줘"
```

**Step 5: dev 브랜치 push**

```bash
git push origin dev
```
