import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_task_list_tool():
    mock_tokens = MagicMock()
    mock_tokens.access_token = "test_token"
    mock_tokens.expires_at = datetime.now(timezone.utc).replace(year=2099)

    mock_service = MagicMock()
    mock_service.tasks.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "1", "title": "테스트 할 일", "status": "needsAction"}]
    }

    with (
        patch(
            "panager.google.tool.get_tokens",
            new_callable=AsyncMock,
            return_value=mock_tokens,
        ),
        patch("panager.google.tool._build_service", return_value=mock_service),
    ):
        from panager.google.tool import task_list

        result = await task_list.ainvoke({"user_id": 123})
        assert "테스트 할 일" in result
