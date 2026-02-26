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


@pytest.mark.asyncio
async def test_restore_schedules_integration(db_pool):
    """DB에 있는 미발송 스케줄 복구 시뮬레이션."""
    mock_provider = MagicMock()
    scheduler = SchedulerService(pool=db_pool, notification_provider=mock_provider)

    # scheduler._scheduler를 Mock으로 교체하여 add_job 호출 확인
    mock_apscheduler = MagicMock()
    scheduler._scheduler = mock_apscheduler

    user_id = 998
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            user_id,
            "test_user_restore",
        )
        # 미래의 미발송 스케줄 2개 추가
        trigger1 = datetime.now(timezone.utc) + timedelta(hours=1)
        trigger2 = datetime.now(timezone.utc) + timedelta(hours=2)

        await conn.execute(
            """
            INSERT INTO schedules (user_id, message, trigger_at, type, payload, sent)
            VALUES ($1, 'msg1', $2, 'notification', NULL, FALSE),
                   ($1, 'msg2', $3, 'command', '{"key": "val"}', FALSE)
            """,
            user_id,
            trigger1,
            trigger2,
        )

    # 실행
    await scheduler.restore_schedules()

    # 검증: add_job이 2번 호출되었는가?
    assert mock_apscheduler.add_job.call_count >= 2
    # 정확한 인자 확인 (일부만)
    calls = mock_apscheduler.add_job.call_args_list
    messages = [c[1]["args"][2] for c in calls]
    assert "msg1" in messages
    assert "msg2" in messages


@pytest.mark.asyncio
async def test_cancel_schedule_integration(db_pool):
    """스케줄 취소 시뮬레이션."""
    mock_provider = MagicMock()
    scheduler = SchedulerService(pool=db_pool, notification_provider=mock_provider)

    # scheduler._scheduler를 Mock으로 교체
    mock_apscheduler = MagicMock()
    scheduler._scheduler = mock_apscheduler

    user_id = 997
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            user_id,
            "test_user_cancel",
        )

    # 1. 스케줄 추가
    trigger_at = datetime.now(timezone.utc) + timedelta(days=1)
    schedule_id = await scheduler.add_schedule(
        user_id=user_id, message="to be cancelled", trigger_at=trigger_at
    )

    # 2. 취소
    success = await scheduler.cancel_schedule(user_id, str(schedule_id))
    assert success is True

    # 3. DB 확인 (삭제되었는지)
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM schedules WHERE id = $1", schedule_id
        )
        assert count == 0

    # 4. 스케줄러 확인 (remove_job 호출되었는지)
    mock_apscheduler.remove_job.assert_called_once_with(str(schedule_id))
