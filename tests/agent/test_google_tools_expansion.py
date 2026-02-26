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
