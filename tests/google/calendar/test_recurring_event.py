import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_recurring_event_create():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_created = {"summary": "주간 회의", "id": "evt_abc"}

    with (
        patch(
            "panager.google.calendar.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
        patch("panager.google.calendar.tool._build_service", return_value=mock_service),
        patch(
            "panager.google.calendar.tool._execute",
            new_callable=AsyncMock,
            return_value=mock_created,
        ),
    ):
        from panager.google.calendar.tool import make_recurring_event_create

        tool = make_recurring_event_create(user_id=123)
        result = await tool.ainvoke(
            {
                "title": "주간 회의",
                "start_at": "2026-02-23T10:00:00+09:00",
                "end_at": "2026-02-23T11:00:00+09:00",
                "rrule": "RRULE:FREQ=WEEKLY;BYDAY=MO",
            }
        )

    assert "주간 회의" in result
    call_kwargs = mock_service.events.return_value.insert.call_args.kwargs
    assert "RRULE:FREQ=WEEKLY;BYDAY=MO" in call_kwargs["body"]["recurrence"][0]


@pytest.mark.asyncio
async def test_recurring_event_create_with_description():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_created = {"summary": "데일리 스탠드업", "id": "evt_xyz"}

    with (
        patch(
            "panager.google.calendar.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
        patch("panager.google.calendar.tool._build_service", return_value=mock_service),
        patch(
            "panager.google.calendar.tool._execute",
            new_callable=AsyncMock,
            return_value=mock_created,
        ),
    ):
        from panager.google.calendar.tool import make_recurring_event_create

        tool = make_recurring_event_create(user_id=123)
        result = await tool.ainvoke(
            {
                "title": "데일리 스탠드업",
                "start_at": "2026-02-23T09:00:00+09:00",
                "end_at": "2026-02-23T09:15:00+09:00",
                "rrule": "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
                "description": "팀 데일리 미팅",
            }
        )

    assert "데일리 스탠드업" in result
    call_kwargs = mock_service.events.return_value.insert.call_args.kwargs
    assert call_kwargs["body"].get("description") == "팀 데일리 미팅"
