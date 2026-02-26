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

@pytest.fixture
def scheduler_service(mock_pool, mock_scheduler):
    return SchedulerService(pool=mock_pool)
