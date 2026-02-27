from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from panager.api.main import create_app
from panager.agent.state import PendingReflection


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.trigger_task = AsyncMock()
    bot.github_service = MagicMock()
    bot.google_service = MagicMock()
    bot.notion_service = MagicMock()
    # Mocking DB response for user_id lookup
    return bot


@pytest.mark.asyncio
async def test_github_webhook_triggers_task_with_pydantic_conversion():
    """GitHub 웹훅 수신 시 bot.trigger_task가 호출되고, bot.py에서 Pydantic 모델로 변환되는지 테스트."""
    mock_bot_instance = MagicMock()
    mock_bot_instance.trigger_task = AsyncMock()

    # We need to test the actual conversion logic in PanagerBot.trigger_task
    from panager.discord.bot import PanagerBot
    from panager.agent.state import PendingReflection

    bot = PanagerBot(
        memory_service=MagicMock(),
        google_service=MagicMock(),
        github_service=MagicMock(),
        notion_service=MagicMock(),
        scheduler_service=MagicMock(),
        registry=MagicMock(),
    )
    bot.graph = MagicMock()
    bot.graph.aget_state = AsyncMock()
    bot.graph.aget_state.return_value = MagicMock(values={})

    # Mock fetch_user and dm for _stream_agent_response
    mock_user = AsyncMock()
    mock_user.__str__ = MagicMock(return_value="test_user")
    bot.fetch_user = AsyncMock(return_value=mock_user)

    payload = {
        "pending_reflections": [
            {
                "repository": "owner/repo",
                "ref": "refs/heads/main",
                "commits": [
                    {"message": "fix: bug", "timestamp": "2023-01-01T00:00:00Z"}
                ],
            }
        ]
    }

    with patch(
        "panager.discord.bot._stream_agent_response", new_callable=AsyncMock
    ) as mock_stream:
        await bot.trigger_task(123, "test command", payload)

        mock_stream.assert_called_once()
        state = mock_stream.call_args[0][1]

        # Verify conversion
        assert isinstance(state["pending_reflections"][0], PendingReflection)
        assert state["pending_reflections"][0].repository == "owner/repo"
        assert state["pending_reflections"][0].commits[0].message == "fix: bug"


def test_github_webhook_endpoint_parsing(mock_bot):
    """FastAPI 엔드포인트에서 페이로드가 올바르게 파싱되어 bot.trigger_task로 전달되는지 테스트."""
    app = create_app(mock_bot)
    client = TestClient(app)

    webhook_data = {
        "repository": {"full_name": "owner/repo"},
        "ref": "refs/heads/main",
        "commits": [{"message": "test commit", "timestamp": "2023-01-01"}],
    }

    # Mock signature verification and DB lookup
    with (
        patch(
            "panager.api.webhooks.verify_signature",
            return_value=json.dumps(webhook_data).encode(),
        ),
        patch("panager.api.webhooks.get_pool") as mock_pool_getter,
    ):
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [{"user_id": 123}]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool_getter.return_value = mock_pool

        response = client.post(
            "/webhooks/github", headers={"X-Hub-Signature-256": "sha256=fake"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # trigger_task 호출 인자 확인
        mock_bot.trigger_task.assert_called_once()
        args, kwargs = mock_bot.trigger_task.call_args
        assert args[0] == 123
        assert "GitHub Push 알림" in args[1]
        assert kwargs["payload"]["pending_reflections"][0]["repository"] == "owner/repo"
