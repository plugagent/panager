import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from contextlib import asynccontextmanager


@pytest.mark.asyncio
async def test_schedule_create_tool():
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)
    new_id = uuid4()

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = new_id

    mock_pool = MagicMock()

    @asynccontextmanager
    async def fake_acquire():
        yield mock_conn

    mock_pool.acquire = fake_acquire

    mock_scheduler = MagicMock()

    with (
        patch("panager.scheduler.tool.get_pool", return_value=mock_pool),
        patch("panager.scheduler.tool.get_scheduler", return_value=mock_scheduler),
    ):
        from panager.scheduler.tool import schedule_create

        result = await schedule_create.ainvoke(
            {
                "message": "회의 알림",
                "trigger_at": future_time.isoformat(),
                "user_id": 123,
            }
        )
        assert "예약" in result
        mock_scheduler.add_job.assert_called_once()
