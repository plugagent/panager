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
        patch(
            "panager.google.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
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
    mock_service.calendarList().list().execute.return_value = {
        "items": [{"id": "primary"}]
    }
    mock_service.events().list().execute.return_value = {"items": []}

    with (
        patch(
            "panager.google.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
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
    mock_service.events().insert().execute.return_value = {
        "id": "new_evt",
        "summary": "새 이벤트",
    }

    with (
        patch(
            "panager.google.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
        patch("panager.google.tool._build_calendar_service", return_value=mock_service),
    ):
        from panager.google.tool import make_event_create

        tool = make_event_create(user_id=123)
        result = await tool.ainvoke(
            {
                "title": "새 이벤트",
                "start_at": "2026-02-21T10:00:00+09:00",
                "end_at": "2026-02-21T11:00:00+09:00",
            }
        )
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
        patch(
            "panager.google.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
        patch("panager.google.tool._build_calendar_service", return_value=mock_service),
    ):
        from panager.google.tool import make_event_update

        tool = make_event_update(user_id=123)
        result = await tool.ainvoke(
            {
                "event_id": "evt1",
                "calendar_id": "primary",
                "title": "수정된 제목",
            }
        )
        assert "수정" in result
        mock_service.events().patch.assert_called_with(
            calendarId="primary", eventId="evt1", body={"summary": "수정된 제목"}
        )


@pytest.mark.asyncio
async def test_event_update_no_fields():
    mock_creds = MagicMock()
    mock_service = MagicMock()

    with (
        patch(
            "panager.google.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
        patch("panager.google.tool._build_calendar_service", return_value=mock_service),
    ):
        from panager.google.tool import make_event_update

        tool = make_event_update(user_id=123)
        result = await tool.ainvoke(
            {
                "event_id": "evt1",
                "calendar_id": "primary",
            }
        )
        assert "수정할 필드" in result
        mock_service.events().patch.assert_not_called()


@pytest.mark.asyncio
async def test_event_delete():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.events().delete().execute.return_value = None

    with (
        patch(
            "panager.google.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
        patch("panager.google.tool._build_calendar_service", return_value=mock_service),
    ):
        from panager.google.tool import make_event_delete

        tool = make_event_delete(user_id=123)
        result = await tool.ainvoke(
            {
                "event_id": "evt1",
                "calendar_id": "primary",
            }
        )
        assert "삭제" in result
