from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from panager.services.scheduler import SchedulerService, NotificationProvider


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.acquire = MagicMock()
    return pool


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    return conn


@pytest.fixture
def mock_scheduler():
    with patch("apscheduler.schedulers.asyncio.AsyncIOScheduler") as mock:
        scheduler_instance = mock.return_value
        yield scheduler_instance


@pytest.fixture
def mock_provider():
    return MagicMock(spec=NotificationProvider)


@pytest.mark.asyncio
async def test_init_starts_scheduler(mock_pool, mock_scheduler):
    service = SchedulerService(pool=mock_pool)
    mock_scheduler.start.assert_called_once()
    assert service._pool == mock_pool
    assert service._scheduler == mock_scheduler


@pytest.mark.asyncio
async def test_set_notification_provider(mock_pool, mock_scheduler, mock_provider):
    service = SchedulerService(pool=mock_pool)
    service.set_notification_provider(mock_provider)
    assert service._notification_provider == mock_provider


@pytest.mark.asyncio
async def test_add_schedule(mock_pool, mock_scheduler, mock_conn):
    service = SchedulerService(pool=mock_pool)
    user_id = 123
    message = "test message"
    trigger_at = datetime.now(timezone.utc)
    type = "notification"
    payload = {"key": "value"}

    # Mock DB interaction
    schedule_id = UUID("12345678-1234-5678-1234-567812345678")
    mock_conn.fetchval.return_value = schedule_id
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    result = await service.add_schedule(user_id, message, trigger_at, type, payload)

    assert result == schedule_id
    mock_conn.fetchval.assert_called_once()
    mock_scheduler.add_job.assert_called_once_with(
        service._execute_schedule,
        "date",
        run_date=trigger_at,
        args=[user_id, str(schedule_id), message, type, payload],
        id=str(schedule_id),
        replace_existing=True,
    )


@pytest.mark.asyncio
async def test_cancel_schedule_success(mock_pool, mock_scheduler, mock_conn):
    service = SchedulerService(pool=mock_pool)
    user_id = 123
    schedule_id = "12345678-1234-5678-1234-567812345678"

    # Mock DB interaction: DELETE returns "DELETE 1"
    mock_conn.execute.return_value = "DELETE 1"
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    result = await service.cancel_schedule(user_id, schedule_id)

    assert result is True
    mock_conn.execute.assert_called_once()
    mock_scheduler.remove_job.assert_called_once_with(schedule_id)


@pytest.mark.asyncio
async def test_cancel_schedule_not_found(mock_pool, mock_scheduler, mock_conn):
    service = SchedulerService(pool=mock_pool)
    user_id = 123
    schedule_id = "12345678-1234-5678-1234-567812345678"

    # Mock DB interaction: DELETE returns "DELETE 0"
    mock_conn.execute.return_value = "DELETE 0"
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    result = await service.cancel_schedule(user_id, schedule_id)

    assert result is False
    mock_conn.execute.assert_called_once()
    mock_scheduler.remove_job.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_schedule_scheduler_error(mock_pool, mock_scheduler, mock_conn):
    service = SchedulerService(pool=mock_pool)
    user_id = 123
    schedule_id = "12345678-1234-5678-1234-567812345678"

    # Mock DB interaction
    mock_conn.execute.return_value = "DELETE 1"
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock scheduler error
    mock_scheduler.remove_job.side_effect = Exception("Job not found")

    result = await service.cancel_schedule(user_id, schedule_id)

    assert result is True  # Should return True even if scheduler removal fails
    mock_scheduler.remove_job.assert_called_once_with(schedule_id)
