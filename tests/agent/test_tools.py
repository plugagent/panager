import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from panager.agent.tools import (
    make_memory_save,
    make_memory_search,
    make_schedule_create,
    make_schedule_cancel,
    make_task_list,
    make_task_create,
    make_task_complete,
    make_event_list,
    make_event_create,
    make_event_update,
    make_event_delete,
)


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
async def test_memory_save_tool(mock_memory_service):
    user_id = 123
    mock_memory_service.save_memory = AsyncMock()

    tool = make_memory_save(user_id, mock_memory_service)
    result = await tool.ainvoke({"content": "테스트 메모리"})

    assert "저장" in result
    mock_memory_service.save_memory.assert_called_once_with(user_id, "테스트 메모리")


@pytest.mark.asyncio
async def test_memory_search_tool(mock_memory_service):
    user_id = 123
    mock_memory_service.search_memories = AsyncMock(
        return_value=["메모리 1", "메모리 2"]
    )

    tool = make_memory_search(user_id, mock_memory_service)
    result = await tool.ainvoke({"query": "검색어", "limit": 2})

    assert "메모리 1" in result
    assert "메모리 2" in result
    mock_memory_service.search_memories.assert_called_once_with(user_id, "검색어", 2)


@pytest.mark.asyncio
async def test_schedule_create_tool(mock_scheduler_service):
    user_id = 123
    mock_scheduler_service.add_schedule = AsyncMock()

    tool = make_schedule_create(user_id, mock_scheduler_service)
    result = await tool.ainvoke(
        {"message": "알람", "trigger_at": "2026-02-22T12:00:00"}
    )

    assert "예약" in result
    mock_scheduler_service.add_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_task_list_tool(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_service.tasks().list().execute = MagicMock(
        return_value={
            "items": [{"id": "t1", "title": "할일 1", "status": "needsAction"}]
        }
    )
    mock_google_service.get_tasks_service = AsyncMock(return_value=mock_service)

    tool = make_task_list(user_id, mock_google_service)
    result = await tool.ainvoke({})

    assert "할일 1" in result
    mock_google_service.get_tasks_service.assert_called_once_with(user_id)


@pytest.mark.asyncio
async def test_event_list_tool(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_service.calendarList().list().execute = MagicMock(
        return_value={"items": [{"id": "primary"}]}
    )
    mock_service.events().list().execute = MagicMock(
        return_value={
            "items": [
                {
                    "id": "e1",
                    "summary": "일정 1",
                    "start": {"dateTime": "2026-02-22T10:00:00+09:00"},
                }
            ]
        }
    )
    mock_google_service.get_calendar_service = AsyncMock(return_value=mock_service)

    tool = make_event_list(user_id, mock_google_service)
    result = await tool.ainvoke({"days_ahead": 7})

    assert "일정 1" in result
    mock_google_service.get_calendar_service.assert_called_once_with(user_id)
