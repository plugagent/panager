import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessageChunk


async def _make_fake_stream(*chunks: str):
    """주어진 텍스트 청크들을 yield하는 가짜 astream async generator."""
    for text in chunks:
        yield (AIMessageChunk(content=text), {"thread_id": "test"})


@pytest.mark.asyncio
async def test_stream_builds_message_incrementally():
    """스트리밍 청크가 누적되어 최종 메시지에 반영되는지 검증."""
    from panager.bot.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()
    mock_graph.astream.return_value = _make_fake_stream("안녕", "하세요", "!")

    state = {"user_id": 1, "username": "test", "messages": [], "memory_context": ""}
    config = {"configurable": {"thread_id": "1"}}

    await _stream_agent_response(mock_graph, state, config, mock_channel)

    final_call = sent_message.edit.call_args
    assert final_call is not None
    assert "안녕하세요!" in final_call.kwargs["content"]
    assert "▌" not in final_call.kwargs["content"]


@pytest.mark.asyncio
async def test_stream_empty_response_sends_fallback():
    """LLM이 빈 응답을 반환할 때 fallback 메시지가 전송되는지 검증."""
    from panager.bot.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()
    mock_graph.astream.return_value = _make_fake_stream()

    state = {"user_id": 1, "username": "test", "messages": [], "memory_context": ""}
    config = {"configurable": {"thread_id": "1"}}

    await _stream_agent_response(mock_graph, state, config, mock_channel)

    mock_channel.send.assert_called_once_with("생각하는 중...")
    sent_message.edit.assert_called_once_with(content="(응답을 받지 못했습니다.)")


@pytest.mark.asyncio
async def test_stream_sends_thinking_message():
    """channel.send('생각하는 중...')가 반드시 1회 호출되는지 검증."""
    from panager.bot.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()
    mock_graph.astream.return_value = _make_fake_stream("hello")

    state = {"user_id": 1, "username": "test", "messages": [], "memory_context": ""}
    config = {"configurable": {"thread_id": "1"}}

    await _stream_agent_response(mock_graph, state, config, mock_channel)

    # "생각하는 중..." 메시지가 반드시 1회 전송 (타이밍 순서는 무관)
    mock_channel.send.assert_called_once_with("생각하는 중...")


@pytest.mark.asyncio
async def test_handle_dm_ignores_message_during_interrupt():
    """interrupt 대기 중에 새 메시지가 오면 안내 메시지만 보내고 graph를 실행하지 않음."""
    from panager.bot.handlers import handle_dm
    import discord
    from unittest.mock import patch

    mock_bot = MagicMock()
    mock_graph = MagicMock()

    # interrupt 중인 snapshot 모킹
    mock_snapshot = MagicMock()
    mock_snapshot.next = ("hitl",)  # 비어있지 않으면 interrupt 중
    mock_graph.aget_state = AsyncMock(return_value=mock_snapshot)
    mock_graph.astream = MagicMock()  # 호출되면 안 됨

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author.bot = False
    mock_message.author.id = 123
    mock_message.author.__str__ = lambda self: "testuser"
    mock_message.content = "새 메시지"
    mock_message.channel = MagicMock(spec=discord.DMChannel)
    mock_message.channel.send = AsyncMock()

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
        )
    )

    with patch("panager.bot.handlers.get_pool", return_value=mock_pool):
        await handle_dm(mock_message, mock_bot, mock_graph)

    mock_graph.astream.assert_not_called()
    mock_message.channel.send.assert_called_once()
    assert "확인" in mock_message.channel.send.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_dm_sends_confirm_view_after_interrupt():
    """astream 후 interrupt가 발생하면 ConfirmView가 전송되는지 검증."""
    from panager.bot.handlers import handle_dm
    import discord
    from unittest.mock import patch

    mock_bot = MagicMock()
    mock_graph = MagicMock()

    tool_call = {"name": "task_delete", "args": {"task_id": "abc"}, "id": "call_1"}
    mock_interrupt = MagicMock()
    mock_interrupt.value = {"tool_call": tool_call}

    mock_task = MagicMock()
    mock_task.interrupts = [mock_interrupt]

    snapshot_before = MagicMock()
    snapshot_before.next = ()  # interrupt 없음

    snapshot_after = MagicMock()
    snapshot_after.next = ("hitl",)  # interrupt 발생
    snapshot_after.tasks = [mock_task]

    mock_graph.aget_state = AsyncMock(side_effect=[snapshot_before, snapshot_after])

    async def fake_stream(*args, **kwargs):
        yield (AIMessageChunk(content="처리 중..."), {})

    mock_graph.astream = MagicMock(return_value=fake_stream())

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author.bot = False
    mock_message.author.id = 123
    mock_message.author.__str__ = lambda self: "testuser"
    mock_message.content = "테스트 삭제해줘"
    mock_channel = AsyncMock(spec=discord.DMChannel)
    mock_channel.send = AsyncMock(return_value=AsyncMock())
    mock_message.channel = mock_channel

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
        )
    )

    with (
        patch("panager.bot.handlers.get_pool", return_value=mock_pool),
        patch("panager.bot.handlers.ConfirmView") as mock_view_cls,
    ):
        mock_view_cls.return_value = MagicMock()
        await handle_dm(mock_message, mock_bot, mock_graph)

    mock_view_cls.assert_called_once()
    # send가 view와 함께 호출됐는지
    calls = mock_channel.send.call_args_list
    view_call = next((c for c in calls if c.kwargs.get("view") is not None), None)
    assert view_call is not None
