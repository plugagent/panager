from __future__ import annotations
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from panager.agent.google.tools import (
    TaskAction,
    CalendarAction,
    make_manage_google_tasks,
    make_manage_google_calendar,
)
from pydantic import ValidationError


@pytest.fixture
def mock_google_service():
    return MagicMock()


@pytest.mark.asyncio
async def test_manage_google_tasks_pagination(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_tasks = mock_service.tasks.return_value

    # Mock two pages of results
    mock_tasks.list.return_value.execute.side_effect = [
        {"items": [{"id": "t1"}], "nextPageToken": "token1"},
        {"items": [{"id": "t2"}]},
    ]
    mock_google_service.get_tasks_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_tasks(user_id, mock_google_service)
    result = json.loads(await tool.ainvoke({"action": TaskAction.LIST}))

    assert len(result["tasks"]) == 2
    assert mock_tasks.list.call_count == 2
    mock_tasks.list.assert_any_call(tasklist="@default", pageToken=None)
    mock_tasks.list.assert_any_call(tasklist="@default", pageToken="token1")


@pytest.mark.asyncio
async def test_manage_google_tasks_validation():
    user_id = 123
    mock_service = MagicMock()
    tool = make_manage_google_tasks(user_id, mock_service)

    with pytest.raises(ValidationError):
        # action='create' requires 'title'
        await tool.ainvoke({"action": TaskAction.CREATE})
    with pytest.raises(ValidationError):
        # action='update_status' requires 'task_id'
        await tool.ainvoke({"action": TaskAction.UPDATE_STATUS, "status": "completed"})
    with pytest.raises(ValidationError):
        # action='delete' requires 'task_id'
        await tool.ainvoke({"action": TaskAction.DELETE})


@pytest.mark.asyncio
async def test_manage_google_calendar_pagination_and_multi_cal(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    # 2 calendars
    mock_service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "cal1"}, {"id": "cal2"}]
    }
    mock_events = mock_service.events.return_value
    # Each calendar returns 1 page
    mock_events.list.return_value.execute.side_effect = [
        {"items": [{"id": "e1"}], "nextPageToken": "t1"},
        {"items": [{"id": "e2"}]},  # Page 2 for cal1
        {"items": [{"id": "e3"}]},  # Page 1 for cal2
    ]
    mock_google_service.get_calendar_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_calendar(user_id, mock_google_service)
    result = json.loads(await tool.ainvoke({"action": CalendarAction.LIST}))

    assert len(result["events"]) == 3
    assert mock_events.list.call_count == 3


@pytest.mark.asyncio
async def test_manage_google_calendar_validation():
    user_id = 123
    mock_service = MagicMock()
    tool = make_manage_google_calendar(user_id, mock_service)

    with pytest.raises(ValidationError):
        # action='create' misses title
        await tool.ainvoke(
            {"action": CalendarAction.CREATE, "start_at": "S", "end_at": "E"}
        )
    with pytest.raises(ValidationError):
        # action='create' misses start_at
        await tool.ainvoke(
            {"action": CalendarAction.CREATE, "title": "T", "end_at": "E"}
        )
    with pytest.raises(ValidationError):
        # action='create' misses end_at
        await tool.ainvoke(
            {"action": CalendarAction.CREATE, "title": "T", "start_at": "S"}
        )
    with pytest.raises(ValidationError):
        # action='delete' requires event_id
        await tool.ainvoke({"action": CalendarAction.DELETE})


@pytest.mark.asyncio
async def test_manage_google_calendar_create(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_events = mock_service.events.return_value
    mock_events.insert.return_value.execute.return_value = {"id": "e_new"}
    mock_google_service.get_calendar_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_calendar(user_id, mock_google_service)
    result = json.loads(
        await tool.ainvoke(
            {
                "action": CalendarAction.CREATE,
                "title": "New Event",
                "start_at": "2026-02-27T09:00:00Z",
                "end_at": "2026-02-27T10:00:00Z",
            }
        )
    )

    assert result["status"] == "success"
    assert result["event"]["id"] == "e_new"


@pytest.mark.asyncio
async def test_manage_google_calendar_delete(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_events = mock_service.events.return_value
    mock_events.delete.return_value.execute.return_value = {}
    mock_google_service.get_calendar_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_calendar(user_id, mock_google_service)
    result = json.loads(
        await tool.ainvoke({"action": CalendarAction.DELETE, "event_id": "e1"})
    )

    assert result["status"] == "success"
    assert result["event_id"] == "e1"


@pytest.mark.asyncio
async def test_manage_google_tasks_create(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_tasks = mock_service.tasks.return_value
    mock_tasks.insert.return_value.execute.return_value = {"id": "t_new"}
    mock_google_service.get_tasks_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_tasks(user_id, mock_google_service)
    result = json.loads(
        await tool.ainvoke({"action": TaskAction.CREATE, "title": "New Task"})
    )
    assert result["status"] == "success"
    assert result["task"]["id"] == "t_new"


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
    result = json.loads(
        await tool.ainvoke(
            {"action": TaskAction.UPDATE_STATUS, "task_id": "t1", "status": "completed"}
        )
    )
    assert result["status"] == "success"
    assert result["task"]["status"] == "completed"


@pytest.mark.asyncio
async def test_manage_google_tasks_delete(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_tasks = mock_service.tasks.return_value
    mock_tasks.delete.return_value.execute.return_value = {}
    mock_google_service.get_tasks_service = AsyncMock(return_value=mock_service)

    tool = make_manage_google_tasks(user_id, mock_google_service)
    result = json.loads(
        await tool.ainvoke({"action": TaskAction.DELETE, "task_id": "t1"})
    )
    assert result["status"] == "success"
    assert result["task_id"] == "t1"
