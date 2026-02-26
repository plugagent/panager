import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from discord import DMChannel, User, Message
from langchain_core.messages import HumanMessage
from panager.discord.bot import PanagerBot


@pytest.fixture
def mock_services():
    return {
        "memory": MagicMock(),
        "google": MagicMock(),
        "github": MagicMock(),
        "notion": MagicMock(),
        "scheduler": MagicMock(),
    }


@pytest.fixture
def bot(mock_services):
    bot = PanagerBot(
        memory_service=mock_services["memory"],
        google_service=mock_services["google"],
        github_service=mock_services["github"],
        notion_service=mock_services["notion"],
        scheduler_service=mock_services["scheduler"],
    )
    bot.graph = MagicMock()
    return bot


@pytest.mark.asyncio
async def test_get_user_lock(bot):
    """Verify that _get_user_lock returns the same lock for the same user."""
    lock1 = bot._get_user_lock(123)
    lock2 = bot._get_user_lock(123)
    lock3 = bot._get_user_lock(456)

    assert lock1 is lock2
    assert isinstance(lock1, asyncio.Lock)
    assert lock1 is not lock3


@pytest.mark.asyncio
async def test_send_notification(bot):
    """Verify that send_notification fetches user and sends DM."""
    user_id = 123
    message = "Test message"

    mock_user = AsyncMock(spec=User)
    mock_dm = AsyncMock(spec=DMChannel)
    mock_user.create_dm.return_value = mock_dm

    bot.fetch_user = AsyncMock(return_value=mock_user)

    await bot.send_notification(user_id, message)

    bot.fetch_user.assert_awaited_once_with(user_id)
    mock_user.create_dm.assert_awaited_once()
    mock_dm.send.assert_awaited_once_with(message)


@pytest.mark.asyncio
async def test_trigger_task(bot):
    """Verify that trigger_task constructs state and calls _stream_agent_response."""
    user_id = 123
    command = "Test command"
    payload = {"pending_reflections": ["some context"]}

    mock_user = AsyncMock(spec=User)
    mock_user.__str__ = MagicMock(return_value="test_user#1234")
    mock_dm = AsyncMock(spec=DMChannel)
    mock_user.create_dm.return_value = mock_dm

    bot.fetch_user = AsyncMock(return_value=mock_user)

    with patch(
        "panager.discord.bot._stream_agent_response", new_callable=AsyncMock
    ) as mock_stream:
        await bot.trigger_task(user_id, command, payload)

        mock_stream.assert_awaited_once()
        args, kwargs = mock_stream.call_args
        # args: (graph, state, config, channel)
        state = args[1]
        assert state["user_id"] == user_id
        assert state["username"] == "test_user#1234"
        assert len(state["messages"]) == 1
        assert isinstance(state["messages"][0], HumanMessage)
        assert state["messages"][0].content == command
        assert state["is_system_trigger"] is True
        assert state["pending_reflections"] == payload["pending_reflections"]

        config = args[2]
        assert config["configurable"]["thread_id"] == str(user_id)
        assert args[3] == mock_dm


@pytest.mark.asyncio
async def test_process_auth_queue(bot):
    """Verify that _process_auth_queue resumes pending messages."""
    user_id = 123
    pending_message = "Pending message"
    bot._pending_messages[user_id] = pending_message

    mock_user = AsyncMock(spec=User)
    mock_dm = AsyncMock(spec=DMChannel)
    mock_user.create_dm.return_value = mock_dm
    bot.fetch_user = AsyncMock(return_value=mock_user)

    # Put event in queue
    await bot.auth_complete_queue.put({"user_id": user_id})

    # We need to run _process_auth_queue in a way that we can stop it
    # Since it's an infinite loop, we'll use a timeout or mock the queue to return once then raise

    with patch(
        "panager.discord.bot._stream_agent_response", new_callable=AsyncMock
    ) as mock_stream:
        # Patch get to return once then raise an exception to break the loop
        original_get = bot.auth_complete_queue.get
        bot.auth_complete_queue.get = AsyncMock(
            side_effect=[{"user_id": user_id}, asyncio.CancelledError()]
        )

        try:
            await bot._process_auth_queue()
        except asyncio.CancelledError:
            pass

        mock_stream.assert_awaited_once()
        args = mock_stream.call_args[0]
        state = args[1]
        assert state["messages"][0].content == pending_message
        assert user_id not in bot._pending_messages


@pytest.mark.asyncio
async def test_on_message_ignores_bot(bot):
    """Verify on_message ignores bot messages."""
    mock_message = MagicMock(spec=Message)
    mock_message.author.bot = True

    with patch("panager.discord.bot.handle_dm", new_callable=AsyncMock) as mock_handle:
        await bot.on_message(mock_message)
        mock_handle.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_ignores_non_dm(bot):
    """Verify on_message ignores non-DM channels."""
    mock_message = MagicMock(spec=Message)
    mock_message.author.bot = False
    mock_message.channel = MagicMock()  # Not a DMChannel

    with patch("panager.discord.bot.handle_dm", new_callable=AsyncMock) as mock_handle:
        await bot.on_message(mock_message)
        mock_handle.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_calls_handle_dm(bot):
    """Verify on_message calls handle_dm for valid DM messages."""
    mock_message = MagicMock(spec=Message)
    mock_message.author.bot = False
    mock_message.author.id = 123
    mock_message.channel = MagicMock(spec=DMChannel)

    with patch("panager.discord.bot.handle_dm", new_callable=AsyncMock) as mock_handle:
        await bot.on_message(mock_message)
        mock_handle.assert_awaited_once_with(mock_message, bot.graph)


@pytest.mark.asyncio
async def test_pending_messages_property(bot):
    """Verify pending_messages property."""
    bot._pending_messages = {123: "hello"}
    assert bot.pending_messages == {123: "hello"}


@pytest.mark.asyncio
async def test_get_user_timezone(bot):
    """Verify get_user_timezone."""
    assert await bot.get_user_timezone(123) == "Asia/Seoul"


@pytest.mark.asyncio
async def test_send_notification_error(bot):
    """Verify send_notification logs exception on error."""
    bot.fetch_user = AsyncMock(side_effect=Exception("Fetch failed"))
    with patch("panager.discord.bot.log") as mock_log:
        await bot.send_notification(123, "msg")
        mock_log.exception.assert_called_with("알림 발송 실패 (user_id=%d)", 123)


@pytest.mark.asyncio
async def test_trigger_task_no_graph(bot):
    """Verify trigger_task returns if graph is None."""
    bot.graph = None
    with patch("panager.discord.bot.log") as mock_log:
        await bot.trigger_task(123, "cmd")
        mock_log.error.assert_called_with("에이전트 그래프가 주입되지 않았습니다.")


@pytest.mark.asyncio
async def test_trigger_task_error(bot):
    """Verify trigger_task logs exception on error."""
    bot.fetch_user = AsyncMock(side_effect=Exception("Trigger failed"))
    with patch("panager.discord.bot.log") as mock_log:
        await bot.trigger_task(123, "cmd")
        mock_log.exception.assert_called_with("태스크 트리거 실패 (user_id=%d)", 123)


@pytest.mark.asyncio
async def test_setup_hook(bot):
    """Verify setup_hook creates background task."""
    with patch("asyncio.create_task") as mock_create:
        await bot.setup_hook()
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_process_auth_queue_skip(bot):
    """Verify _process_auth_queue skips if no pending message or graph."""
    # Case 1: no pending message
    await bot.auth_complete_queue.put({"user_id": 999})
    # Case 2: no graph
    bot._pending_messages[888] = "msg"
    bot.graph = None
    await bot.auth_complete_queue.put({"user_id": 888})

    bot.auth_complete_queue.get = AsyncMock(
        side_effect=[{"user_id": 999}, {"user_id": 888}, asyncio.CancelledError()]
    )

    with patch(
        "panager.discord.bot._stream_agent_response", new_callable=AsyncMock
    ) as mock_stream:
        try:
            await bot._process_auth_queue()
        except asyncio.CancelledError:
            pass
        mock_stream.assert_not_called()


@pytest.mark.asyncio
async def test_process_auth_queue_error(bot):
    """Verify _process_auth_queue logs exception on error."""
    user_id = 123
    bot._pending_messages[user_id] = "msg"
    bot.fetch_user = AsyncMock(side_effect=Exception("Process failed"))

    bot.auth_complete_queue.get = AsyncMock(
        side_effect=[{"user_id": user_id}, asyncio.CancelledError()]
    )

    with patch("panager.discord.bot.log") as mock_log:
        try:
            await bot._process_auth_queue()
        except asyncio.CancelledError:
            pass
        mock_log.exception.assert_called_with(
            "인증 후 재실행 실패 (user_id=%d)", user_id
        )


@pytest.mark.asyncio
async def test_on_ready(bot):
    """Verify on_ready logging."""
    with (
        patch.object(PanagerBot, "user", "bot#1234"),
        patch("panager.discord.bot.log") as mock_log,
    ):
        await bot.on_ready()
        mock_log.info.assert_called_with("봇 로그인 완료: %s", "bot#1234")


@pytest.mark.asyncio
async def test_on_message_no_graph(bot):
    """Verify on_message handles missing graph."""
    bot.graph = None
    mock_message = MagicMock(spec=Message)
    mock_message.author.bot = False
    mock_message.channel = MagicMock(spec=DMChannel)
    mock_message.channel.send = AsyncMock()

    with patch("panager.discord.bot.log") as mock_log:
        await bot.on_message(mock_message)
        mock_log.error.assert_called_with("에이전트 그래프가 주입되지 않았습니다.")
        mock_message.channel.send.assert_awaited_once_with(
            "시스템 준비 중입니다. 잠시 후 다시 시도해주세요."
        )


@pytest.mark.asyncio
async def test_close(bot):
    """Verify close calls super().close()."""
    with patch("discord.Client.close", new_callable=AsyncMock) as mock_super_close:
        await bot.close()
        mock_super_close.assert_awaited_once()
