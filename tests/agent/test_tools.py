import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from panager.tools.google import (
    CalendarAction,
    TaskAction,
    make_manage_google_calendar,
    make_manage_google_tasks,
)
from panager.tools.memory import MemoryAction, make_manage_user_memory
from panager.tools.scheduler import ScheduleAction, make_manage_dm_scheduler


@pytest.fixture
def mock_memory_service():
    return MagicMock()


@pytest.fixture
def mock_google_service():
    return MagicMock()


@pytest.fixture
def mock_scheduler_service():
    return MagicMock()


@pytest.mark.asyncio
async def test_manage_user_memory_save(mock_memory_service):
    user_id = 123
    mock_memory_service.save_memory = AsyncMock()

    tool = make_manage_user_memory(user_id, mock_memory_service)
    result_str = await tool.ainvoke(
        {"action": MemoryAction.SAVE, "content": "테스트 메모리"}
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["action"] == "save"
    assert "테스트 메모리" in result["content_preview"]
    mock_memory_service.save_memory.assert_called_once_with(user_id, "테스트 메모리")


@pytest.mark.asyncio
async def test_manage_user_memory_search(mock_memory_service):
    user_id = 123
    mock_memory_service.search_memories = AsyncMock(
        return_value=["메모리 1", "메모리 2"]
    )

    tool = make_manage_user_memory(user_id, mock_memory_service)
    result_str = await tool.ainvoke(
        {"action": MemoryAction.SEARCH, "query": "검색어", "limit": 2}
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["action"] == "search"
    assert len(result["results"]) == 2
    assert "메모리 1" in result["results"]
    mock_memory_service.search_memories.assert_called_once_with(user_id, "검색어", 2)


@pytest.mark.asyncio
async def test_manage_dm_scheduler_create(mock_scheduler_service):
    user_id = 123
    mock_scheduler_service.add_schedule = AsyncMock(return_value="job_123")

    tool = make_manage_dm_scheduler(user_id, mock_scheduler_service)
    result_str = await tool.ainvoke(
        {
            "action": ScheduleAction.CREATE,
            "command": "알람",
            "trigger_at": "2026-02-22T12:00:00+09:00",
        }
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["action"] == "create"
    assert result["schedule_id"] == "job_123"
    mock_scheduler_service.add_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_manage_dm_scheduler_cancel(mock_scheduler_service):
    user_id = 123
    mock_scheduler_service.cancel_schedule = AsyncMock(return_value=True)

    tool = make_manage_dm_scheduler(user_id, mock_scheduler_service)
    result_str = await tool.ainvoke(
        {"action": ScheduleAction.CANCEL, "schedule_id": "job_123"}
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["action"] == "cancel"
    assert result["schedule_id"] == "job_123"
    mock_scheduler_service.cancel_schedule.assert_called_once_with(user_id, "job_123")


@pytest.mark.asyncio
async def test_manage_google_tasks_list(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_tasks = mock_service.tasks.return_value
    mock_tasks.list.return_value.execute.return_value = {
        "items": [{"id": "t1", "title": "할일 1", "status": "needsAction"}]
    }
    mock_google_service.get_tasks_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_tasks(user_id, mock_google_service)
    result_str = await tool.ainvoke({"action": TaskAction.LIST})
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["tasks"][0]["title"] == "할일 1"
    mock_tasks.list.assert_called_once_with(tasklist="@default", pageToken=None)


@pytest.mark.asyncio
async def test_manage_google_tasks_create(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_tasks = mock_service.tasks.return_value
    mock_tasks.insert.return_value.execute.return_value = {
        "id": "t2",
        "title": "새 할일",
    }
    mock_google_service.get_tasks_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_tasks(user_id, mock_google_service)
    result_str = await tool.ainvoke({"action": TaskAction.CREATE, "title": "새 할일"})
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["task"]["title"] == "새 할일"
    mock_tasks.insert.assert_called_once_with(
        tasklist="@default", body={"title": "새 할일"}
    )


@pytest.mark.asyncio
async def test_manage_google_tasks_update_status(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_tasks = mock_service.tasks.return_value
    mock_tasks.patch.return_value.execute.return_value = {
        "id": "t1",
        "status": "completed",
    }
    mock_google_service.get_tasks_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_tasks(user_id, mock_google_service)
    result_str = await tool.ainvoke(
        {"action": TaskAction.UPDATE_STATUS, "task_id": "t1", "status": "completed"}
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["task"]["status"] == "completed"
    mock_tasks.patch.assert_called_once_with(
        tasklist="@default", task="t1", body={"status": "completed"}
    )


@pytest.mark.asyncio
async def test_manage_google_tasks_delete(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_tasks = mock_service.tasks.return_value
    mock_tasks.delete.return_value.execute.return_value = {}
    mock_google_service.get_tasks_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_tasks(user_id, mock_google_service)
    result_str = await tool.ainvoke({"action": TaskAction.DELETE, "task_id": "t1"})
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["task_id"] == "t1"
    mock_tasks.delete.assert_called_once_with(tasklist="@default", task="t1")


@pytest.mark.asyncio
async def test_manage_google_calendar_list(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "primary"}]
    }
    mock_events = mock_service.events.return_value
    mock_events.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "e1",
                "summary": "일정 1",
                "start": {"dateTime": "2026-02-22T10:00:00+09:00"},
            }
        ]
    }
    mock_google_service.get_calendar_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_calendar(user_id, mock_google_service)
    result_str = await tool.ainvoke({"action": CalendarAction.LIST, "days_ahead": 7})
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["events"][0]["summary"] == "일정 1"
    mock_google_service.get_calendar_service.assert_called_once_with(user_id)


@pytest.mark.asyncio
async def test_manage_google_calendar_create(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_events = mock_service.events.return_value
    mock_events.insert.return_value.execute.return_value = {
        "id": "e2",
        "summary": "새 일정",
    }
    mock_google_service.get_calendar_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_calendar(user_id, mock_google_service)
    result_str = await tool.ainvoke(
        {
            "action": CalendarAction.CREATE,
            "title": "새 일정",
            "start_at": "2026-02-22T10:00:00+09:00",
            "end_at": "2026-02-22T11:00:00+09:00",
        }
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["event"]["summary"] == "새 일정"
    mock_events.insert.assert_called_once_with(
        calendarId="primary",
        body={
            "summary": "새 일정",
            "start": {"dateTime": "2026-02-22T10:00:00+09:00"},
            "end": {"dateTime": "2026-02-22T11:00:00+09:00"},
        },
    )


@pytest.mark.asyncio
async def test_manage_google_calendar_delete(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_events = mock_service.events.return_value
    mock_events.delete.return_value.execute.return_value = {}
    mock_google_service.get_calendar_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_calendar(user_id, mock_google_service)
    result_str = await tool.ainvoke(
        {"action": CalendarAction.DELETE, "event_id": "e1", "calendar_id": "primary"}
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["event_id"] == "e1"
    mock_events.delete.assert_called_once_with(calendarId="primary", eventId="e1")
