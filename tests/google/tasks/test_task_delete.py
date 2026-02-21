import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_task_delete_tool():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.tasks.return_value.delete.return_value = MagicMock()

    with (
        patch(
            "panager.google.tasks.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
        patch("panager.google.tasks.tool._build_service", return_value=mock_service),
        patch(
            "panager.google.tasks.tool._execute",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        from panager.google.tasks.tool import make_task_delete

        tool = make_task_delete(user_id=123)
        result = await tool.ainvoke({"task_id": "abc123"})

    assert "삭제" in result
    mock_service.tasks.return_value.delete.assert_called_once_with(
        tasklist="@default", task="abc123"
    )
