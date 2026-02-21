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
