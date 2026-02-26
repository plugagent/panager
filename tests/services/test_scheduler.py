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
