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


@pytest.mark.asyncio
async def test_execute_schedule_notification_success(
    mock_pool, mock_conn, mock_provider
):
    service = SchedulerService(pool=mock_pool, notification_provider=mock_provider)
    user_id = 123
    schedule_id = "12345678-1234-5678-1234-567812345678"
    message = "test message"

    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    await service._execute_schedule(user_id, schedule_id, message, type="notification")

    mock_provider.send_notification.assert_called_once_with(user_id, message)
    mock_conn.execute.assert_called_once()
    assert "UPDATE schedules SET sent = TRUE" in mock_conn.execute.call_args[0][0]


@pytest.mark.asyncio
async def test_execute_schedule_command_success(mock_pool, mock_conn, mock_provider):
    service = SchedulerService(pool=mock_pool, notification_provider=mock_provider)
    user_id = 123
    schedule_id = "12345678-1234-5678-1234-567812345678"
    message = "test command"
    payload = {"depth": 1}

    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    await service._execute_schedule(
        user_id, schedule_id, message, type="command", payload=payload
    )

    mock_provider.trigger_task.assert_called_once_with(user_id, message, payload)
    mock_conn.execute.assert_called_once()
    assert "UPDATE schedules SET sent = TRUE" in mock_conn.execute.call_args[0][0]


@pytest.mark.asyncio
async def test_execute_schedule_no_provider(mock_pool, caplog):
    service = SchedulerService(pool=mock_pool, notification_provider=None)
    user_id = 123

    await service._execute_schedule(user_id, "sid", "msg")

    assert "알림 제공자가 설정되지 않아" in caplog.text


@pytest.mark.asyncio
async def test_execute_schedule_retry_success(mock_pool, mock_conn, mock_provider):
    service = SchedulerService(pool=mock_pool, notification_provider=mock_provider)
    user_id = 123
    schedule_id = "12345678-1234-5678-1234-567812345678"

    # 1st call fails, 2nd succeeds
    mock_provider.send_notification.side_effect = [Exception("Fail"), None]
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        await service._execute_schedule(user_id, schedule_id, "msg")

        assert mock_provider.send_notification.call_count == 2
        mock_sleep.assert_called_once_with(1)  # 2**0
        mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_execute_schedule_max_retries_exceeded(mock_pool, mock_provider, caplog):
    service = SchedulerService(pool=mock_pool, notification_provider=mock_provider)
    user_id = 123
    schedule_id = "12345678-1234-5678-1234-567812345678"

    # All attempts fail
    mock_provider.send_notification.side_effect = Exception("Permanent Fail")

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        await service._execute_schedule(user_id, schedule_id, "msg")

        assert mock_provider.send_notification.call_count == 4  # 1 initial + 3 retries
        assert mock_sleep.call_count == 3
        assert "스케줄 실행 최대 재시도 초과" in caplog.text
