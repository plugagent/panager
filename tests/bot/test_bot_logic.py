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
    mock_user.__str__.return_value = "test_user#1234"
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
