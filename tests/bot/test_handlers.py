import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from langchain_core.messages import AIMessageChunk, HumanMessage
import asyncio


async def _make_fake_stream(*chunks: str):
    """주어진 텍스트 청크들을 yield하는 가짜 astream async generator."""
    for text in chunks:
        yield (AIMessageChunk(content=text), {"thread_id": "test"})


@pytest.mark.asyncio
async def test_stream_builds_message_incrementally():
    """스트리밍 청크가 누적되어 최종 메시지에 반영되는지 검증."""
    from panager.discord.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()
    mock_graph.astream.return_value = _make_fake_stream("안녕", "하세요", "!")

    state = {"user_id": 1, "username": "test", "messages": [], "memory_context": ""}
    config = {"configurable": {"thread_id": "1"}}

    # Mock time to ensure debounce allows editing
    with patch("time.monotonic", side_effect=[0.0, 1.0, 2.0, 3.0, 4.0]):
        await _stream_agent_response(mock_graph, state, config, mock_channel)

    # 최종 edit은 완성된 텍스트로 호출되어야 함
    final_call = sent_message.edit.call_args
    assert final_call is not None
    assert "안녕하세요!" in final_call.kwargs["content"]
    # 커서(▌)가 최종 텍스트에 없어야 함
    assert "▌" not in final_call.kwargs["content"]


@pytest.mark.asyncio
async def test_stream_empty_response_sends_fallback():
    """LLM이 빈 응답을 반환할 때 fallback 메시지가 전송되는지 검증."""
    from panager.discord.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()
    mock_graph.astream.return_value = _make_fake_stream()  # 빈 스트림

    state = {"user_id": 1, "username": "test", "messages": [], "memory_context": ""}
    config = {"configurable": {"thread_id": "1"}}

    await _stream_agent_response(mock_graph, state, config, mock_channel)

    # 빈 스트림 → "생각하는 중..." 전송 후 fallback 텍스트로 edit
    mock_channel.send.assert_called_once_with("생각하는 중...")
    sent_message.edit.assert_called_once_with(content="(응답을 받지 못했습니다.)")


@pytest.mark.asyncio
async def test_stream_sends_initial_cursor_message():
    """첫 토큰 수신 즉시 초기 메시지(▌)를 전송하는지 검증."""
    from panager.discord.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()
    mock_graph.astream.return_value = _make_fake_stream("hello")

    state = {"user_id": 1, "username": "test", "messages": [], "memory_context": ""}
    config = {"configurable": {"thread_id": "1"}}

    await _stream_agent_response(mock_graph, state, config, mock_channel)

    # "생각하는 중..." 메시지가 astream 전에 즉시 전송되어야 함
    mock_channel.send.assert_called_with("생각하는 중...")


@pytest.mark.asyncio
async def test_stream_debounce_logic():
    """디바운스 로직이 작동하여 너무 빈번한 edit 호출을 방지하는지 검증."""
    from panager.discord.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()
    # 3개의 청크
    mock_graph.astream.return_value = _make_fake_stream("a", "b", "c")

    state = {"user_id": 1, "username": "test", "messages": []}
    config = {"configurable": {"thread_id": "1"}}

    # time.monotonic이 거의 변하지 않도록 설정 (STREAM_DEBOUNCE = 0.2)
    # first call in _stream_agent_response for last_edit_at is not there, it's initialized to 0.0
    # Inside loop: now = time.monotonic()
    with patch("time.monotonic", side_effect=[0.01, 0.02, 0.03, 0.04]):
        await _stream_agent_response(mock_graph, state, config, mock_channel)

    # a, b, c 청크에 대해 0.01, 0.02, 0.03이 반환됨.
    # initial last_edit_at = 0.0
    # 0.01 - 0.0 >= 0.2 is False -> no edit
    # 0.02 - 0.0 >= 0.2 is False -> no edit
    # 0.03 - 0.0 >= 0.2 is False -> no edit
    # Finally, 1 edit for the finished text.
    assert sent_message.edit.call_count == 1
    sent_message.edit.assert_called_once_with(content="abc")


@pytest.mark.asyncio
async def test_stream_deletes_excess_messages():
    """응답이 생각보다 짧을 경우 남은 대기 메시지들이 삭제되는지 검증."""
    from panager.discord.handlers import _stream_agent_response, MAX_MESSAGE_LENGTH

    mock_channel = MagicMock()
    msg1 = AsyncMock()
    msg2 = AsyncMock()
    msg3 = AsyncMock()

    # send calls: 1 (thinking), then possibly more if long
    # We want to simulate multiple messages sent then deleted
    mock_channel.send = AsyncMock(side_effect=[msg1, msg2, msg3])

    mock_graph = MagicMock()
    # Long first chunk to trigger second message, then short final
    long_text = "x" * (MAX_MESSAGE_LENGTH + 1)
    mock_graph.astream.return_value = _make_fake_stream(long_text)

    state = {"user_id": 1, "username": "test", "messages": []}
    config = {"configurable": {"thread_id": "1"}}

    # last_edit_at = 0.0
    # now = 1.0 (>= 0.2) -> current_msg_index = 1 -> sends msg2
    with patch("time.monotonic", side_effect=[1.0, 2.0]):
        await _stream_agent_response(mock_graph, state, config, mock_channel)

    # sent_messages should have [msg1, msg2]
    # chunks will have [MAX_MESSAGE_LENGTH, 1]
    # msg1.edit(content=chunk[0])
    # msg2.edit(content=chunk[1])
    # No messages to delete
    msg2.delete.assert_not_called()

    # Now test actual deletion
    mock_channel.send = AsyncMock(side_effect=[msg1, msg2, msg3])
    # Simulate a case where accumulated length decreases?
    # Content doesn't decrease, but sent_messages can be longer than chunks if we logic it.
    # Actually, the only way sent_messages > chunks is if we sent "..." for a chunk index that we later didn't fill?
    # Wait, the logic says `while len(sent_messages) <= current_msg_index: new_msg = await channel.send("...")`
    # If accumulated is short, but we somehow sent many messages?

    # Let's mock a scenario where current_msg_index was high, but final chunks are few.
    # This might happen if MAX_MESSAGE_LENGTH was smaller during streaming? No.
    # Ah, if we have 2 sent messages but only 1 chunk.

    with patch("panager.discord.handlers.MAX_MESSAGE_LENGTH", 10):
        mock_graph.astream.return_value = _make_fake_stream("0123456789", "a")
        # now=1.0 -> current_msg_index = 1 -> sends msg2. total sent [msg1, msg2]
        # final full_text = "0123456789a" (len 11)
        # chunks = ["0123456789", "a"]
        # Still 2 messages.

        # What if we have msg1 (thinking), then we send msg2 "...", then final text is short?
        mock_graph.astream.return_value = _make_fake_stream("short")
        # To get msg2 sent, current_msg_index must be >= 1.
        # current_msg_index = len(accumulated) // MAX_MESSAGE_LENGTH
        # If accumulated is "0123456789a", current_msg_index = 1.
        # But if we then set full_text = accumulated.strip() and it becomes shorter?
        # accumulated = "          " -> full_text = "" -> fallback "(응답을 받지 못했습니다.)"

        mock_graph.astream.return_value = _make_fake_stream(" " * 20)
        # streaming: accumulated=" " * 20. current_msg_index = 2.
        # sent_messages = [msg1, msg2, msg3]
        # end: full_text = "(응답을 받지 못했습니다.)" (len 15 approx)
        # chunks = ["(응답을 받지..."] if MAX_MESSAGE_LENGTH is 10.
        # chunks will have 2 items.
        # msg1.edit, msg2.edit. msg3.delete() should be called.

        with patch("time.monotonic", side_effect=[1.0, 2.0, 3.0]):
            await _stream_agent_response(mock_graph, state, config, mock_channel)

        msg3.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_dm_registers_user_and_calls_stream():
    """handle_dm이 사용자를 DB에 등록하고 에이전트 응답 스트리밍을 시작하는지 검증."""
    from panager.discord.handlers import handle_dm

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author.id = 123
    mock_message.author.__str__.return_value = "test_user#1234"
    mock_message.content = "hello"
    mock_message.channel = AsyncMock()

    mock_graph = MagicMock()

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with (
        patch("panager.discord.handlers.get_pool", return_value=mock_pool),
        patch(
            "panager.discord.handlers._stream_agent_response", new_callable=AsyncMock
        ) as mock_stream,
    ):
        await handle_dm(mock_message, mock_graph)

        # DB insertion check
        mock_conn.execute.assert_awaited_once()
        args = mock_conn.execute.call_args[0]
        assert "INSERT INTO users" in args[0]
        assert args[1] == 123
        assert args[2] == "test_user#1234"

        # Stream response check
        mock_stream.assert_awaited_once()
        args = mock_stream.call_args[0]
        assert args[0] == mock_graph
        assert args[1]["user_id"] == 123
        assert args[1]["messages"][0].content == "hello"


@pytest.mark.asyncio
async def test_stream_skips_invalid_chunks():
    """Verify that non-string chunks or empty chunks are skipped."""
    from panager.discord.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()

    async def fake_stream():
        # Use MagicMock instead of AIMessageChunk to avoid validation errors
        chunk1 = MagicMock()
        chunk1.content = 123
        yield (chunk1, {})  # Not a string

        chunk2 = MagicMock()
        chunk2.content = ""
        yield (chunk2, {})  # Empty

        yield (AIMessageChunk(content="valid"), {})

    mock_graph.astream.return_value = fake_stream()

    state = {"user_id": 1, "username": "test", "messages": []}
    config = {"configurable": {"thread_id": "1"}}

    # Mock time to trigger edit
    with patch("time.monotonic", side_effect=[0.0, 1.0, 2.0, 3.0]):
        await _stream_agent_response(mock_graph, state, config, mock_channel)

    sent_message.edit.assert_called_with(content="valid")


@pytest.mark.asyncio
async def test_stream_delete_error_handled():
    """Verify that delete errors are caught."""
    from panager.discord.handlers import _stream_agent_response

    mock_channel = MagicMock()
    thinking_msg = AsyncMock()
    msg2 = AsyncMock()
    msg3 = AsyncMock()
    msg3.delete.side_effect = Exception("Delete failed")

    # Use unique mocks for each send call
    mock_channel.send = AsyncMock(side_effect=[thinking_msg, msg2, msg3])

    # current_msg_index = 2 -> sends msg2, msg3
    # final full_text is short -> msg3.delete() is called
    mock_graph = MagicMock()
    mock_graph.astream.return_value = _make_fake_stream(" " * 20)

    state = {"user_id": 1, "username": "test", "messages": []}
    config = {"configurable": {"thread_id": "1"}}

    with (
        patch("panager.discord.handlers.MAX_MESSAGE_LENGTH", 10),
        patch("time.monotonic", side_effect=[0.3, 1.0, 2.0, 3.0]),
    ):
        await _stream_agent_response(mock_graph, state, config, mock_channel)

    msg3.delete.assert_awaited_once()
    # Should not raise exception
