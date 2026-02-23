from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from panager.services.scheduler import SchedulerService
from panager.db.connection import init_pool, close_pool, get_pool


@pytest.fixture
async def db_pool():
    dsn = "postgresql://panager:panager@localhost:5433/panager_test"
    await init_pool(dsn)
    pool = get_pool()
    yield pool
    await close_pool()


@pytest.mark.asyncio
async def test_scheduler_command_simulation(db_pool):
    """에이전트 명령 예약 및 실행 시뮬레이션."""
    mock_provider = MagicMock()
    mock_provider.trigger_task = AsyncMock()
    mock_provider.send_notification = AsyncMock()

    scheduler = SchedulerService(pool=db_pool, notification_provider=mock_provider)

    user_id = 999
    # 먼저 사용자 생성
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            user_id,
            "test_user",
        )

    command = "내일 일정 요약해줘"
    trigger_at = datetime.now(timezone.utc) + timedelta(seconds=1)

    # 1. 예약 (type='command')
    schedule_id = await scheduler.add_schedule(
        user_id=user_id,
        message=command,
        trigger_at=trigger_at,
        type="command",
        payload={"depth": 1},
    )

    # 2. DB 확인
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT type, message, payload FROM schedules WHERE id = $1", schedule_id
        )
        assert row["type"] == "command"
        assert row["message"] == command
        import json

        assert json.loads(row["payload"]) == {"depth": 1}

    # 3. 실행 시뮬레이션 (APScheduler가 호출하는 내부 메서드 직접 호출)
    await scheduler._execute_schedule(
        user_id=user_id,
        schedule_id=str(schedule_id),
        message=command,
        type="command",
        payload={"depth": 1},
    )

    # 4. 검증: trigger_task가 호출되었는가?
    mock_provider.trigger_task.assert_called_once_with(user_id, command, {"depth": 1})
    mock_provider.send_notification.assert_not_called()

    # 5. DB 상태 확인 (sent = True)
    async with db_pool.acquire() as conn:
        sent = await conn.fetchval(
            "SELECT sent FROM schedules WHERE id = $1", schedule_id
        )
        assert sent is True
