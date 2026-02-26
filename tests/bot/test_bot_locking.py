from __future__ import annotations

import asyncio
import discord
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from panager.discord.bot import PanagerBot


@pytest.fixture
def mock_services():
    return {
        "memory": MagicMock(),
        "google": MagicMock(),
        "github": MagicMock(),
        "notion": MagicMock(),
        "scheduler": MagicMock(),
        "registry": MagicMock(),
    }


@pytest.mark.asyncio
async def test_bot_lock_prevents_concurrent_access(mock_services):
    bot = PanagerBot(
        memory_service=mock_services["memory"],
        google_service=mock_services["google"],
        github_service=mock_services["github"],
        notion_service=mock_services["notion"],
        scheduler_service=mock_services["scheduler"],
        registry=mock_services["registry"],
    )
    bot.graph = MagicMock()

    user_id = 123
    execution_order = []

    async def fake_handle_dm(message, graph):
        execution_order.append(f"start_{message.content}")
        await asyncio.sleep(0.1)  # 작업 시뮬레이션
        execution_order.append(f"end_{message.content}")

    with patch("panager.discord.bot.handle_dm", side_effect=fake_handle_dm):
        # 두 개의 메시지를 거의 동시에 보냄
        msg1 = MagicMock()
        msg1.author.id = user_id
        msg1.author.bot = False
        msg1.channel = MagicMock(spec=discord.DMChannel)
        msg1.content = "msg1"

        msg2 = MagicMock()
        msg2.author.id = user_id
        msg2.author.bot = False
        msg2.channel = MagicMock(spec=discord.DMChannel)
        msg2.content = "msg2"

        # 동시에 실행 시도
        await asyncio.gather(
            bot.on_message(msg1),
            bot.on_message(msg2),
        )

    # 결과는 순차적이어야 함 (start1 -> end1 -> start2 -> end2 또는 그 반대)
    # 락이 없다면 start1 -> start2 -> end1 -> end2 식이 될 수 있음
    assert execution_order[0].startswith("start")
    assert execution_order[1].startswith("end")
    assert execution_order[2].startswith("start")
    assert execution_order[3].startswith("end")


@pytest.mark.asyncio
async def test_bot_trigger_task_uses_lock(mock_services):
    """trigger_task 호출 시에도 동일 사용자 락을 사용하는지 확인."""
    bot = PanagerBot(
        memory_service=mock_services["memory"],
        google_service=mock_services["google"],
        github_service=mock_services["github"],
        notion_service=mock_services["notion"],
        scheduler_service=mock_services["scheduler"],
        registry=mock_services["registry"],
    )
    bot.graph = MagicMock()

    user_id = 123
    execution_order = []

    async def fake_stream_response(graph, state, config, dm):
        execution_order.append("start_trigger")
        await asyncio.sleep(0.1)
        execution_order.append("end_trigger")

    async def fake_handle_dm(message, graph):
        execution_order.append("start_dm")
        await asyncio.sleep(0.1)
        execution_order.append("end_dm")

    with (
        patch(
            "panager.discord.bot._stream_agent_response",
            side_effect=fake_stream_response,
        ),
        patch("panager.discord.bot.handle_dm", side_effect=fake_handle_dm),
        patch.object(bot, "fetch_user", return_value=AsyncMock()),
    ):
        msg = MagicMock()
        msg.author.id = user_id
        msg.author.bot = False
        msg.channel = MagicMock(spec=discord.DMChannel)
        msg.content = "user message"

        # DM 수신과 예약 태스크 트리거가 동시에 발생
        await asyncio.gather(
            bot.on_message(msg),
            bot.trigger_task(user_id, "scheduled command"),
        )

    # 순차적 실행 확인
    assert len(execution_order) == 4
    assert execution_order[0].startswith("start")
    assert execution_order[1].startswith("end")
    assert execution_order[2].startswith("start")
    assert execution_order[3].startswith("end")
