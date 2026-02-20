import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager


@pytest.mark.asyncio
async def test_restore_pending_schedules():
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": "uuid-1",
            "user_id": 123,
            "message": "테스트 알림",
            "trigger_at": future_time,
        }
    ]

    mock_pool = MagicMock()

    @asynccontextmanager
    async def fake_acquire():
        yield mock_conn

    mock_pool.acquire = fake_acquire

    mock_scheduler = MagicMock()
    mock_bot = MagicMock()

    with (
        patch("panager.scheduler.runner.get_pool", return_value=mock_pool),
        patch("panager.scheduler.runner._scheduler", mock_scheduler),
    ):
        from panager.scheduler.runner import restore_pending_schedules

        await restore_pending_schedules(mock_bot)
        mock_scheduler.add_job.assert_called_once()
