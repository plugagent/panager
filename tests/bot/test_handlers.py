import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from langchain_core.messages import AIMessageChunk


async def _make_fake_stream(*chunks: str):
    """updates와 messages 이벤트를 혼합하여 yield하는 가짜 astream."""
    # 1. Discovery 시작 (updates)
    yield ("updates", {"discovery": {"discovered_tools": []}})
    # 2. Agent 시작
    yield ("updates", {"agent": {"messages": []}})

    # 3. 메시지 스트리밍
    for text in chunks:
        yield (
            "messages",
            (AIMessageChunk(content=text), {"langgraph_node": "agent"}),
        )

    # 4. 종료 또는 도구 실행 (여기서는 종료 시뮬레이션)
    yield ("updates", {"agent": {"next_worker": "FINISH"}})


def _setup_mock_graph():
    mock_graph = MagicMock()
    mock_graph.aget_state = AsyncMock()
    # Default state return value
    state_mock = MagicMock()
    state_mock.values = {}
    mock_graph.aget_state.return_value = state_mock
    return mock_graph


@pytest.mark.asyncio
async def test_stream_builds_message_incrementally():
    """스트리밍 청크가 누적되어 최종 메시지에 반영되는지 검증."""
    from panager.discord.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = _setup_mock_graph()
    mock_graph.astream.return_value = _make_fake_stream("안녕", "하세요", "!")

    state = {"user_id": 1, "username": "test", "messages": []}
    config = {"configurable": {"thread_id": "1"}}

    # Mock time to ensure debounce allows editing
    with patch(
        "time.monotonic", side_effect=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    ):
        await _stream_agent_response(mock_graph, state, config, mock_channel)

    # 최종 edit은 완성된 텍스트로 호출되어야 함
    # (finalize 호출 시 커서와 상태 메시지가 제거됨)
    sent_message.edit.assert_called_with(content="안녕하세요!")


@pytest.mark.asyncio
async def test_stream_empty_response_sends_fallback():
    """LLM이 빈 응답을 반환할 때 fallback 메시지가 전송되는지 검증."""
    from panager.discord.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = _setup_mock_graph()
    mock_graph.astream.return_value = _make_fake_stream()  # 메시지 청크 없음

    state = {"user_id": 1, "username": "test", "messages": []}
    config = {"configurable": {"thread_id": "1"}}

    await _stream_agent_response(mock_graph, state, config, mock_channel)

    # 빈 스트림 → fallback 텍스트로 edit
    sent_message.edit.assert_called_with(content="(응답을 받지 못했습니다.)")


@pytest.mark.asyncio
async def test_stream_sends_initial_message():
    """실행 시작 시 '생각하는 중...' 메시지를 전송하는지 검증."""
    from panager.discord.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = _setup_mock_graph()
    mock_graph.astream.return_value = _make_fake_stream("hello")

    state = {"user_id": 1, "username": "test", "messages": []}
    config = {"configurable": {"thread_id": "1"}}

    await _stream_agent_response(mock_graph, state, config, mock_channel)

    # 초기 메시지 전송 확인 (상태 업데이트가 즉시 발생하므로 discovery 상태가 포함될 수 있음)
    # 실제로는 _render가 호출되면서 현재 상태가 반영됨
    # Exact match보다는 호출 여부를 확인하거나 유연하게 체크
    mock_channel.send.assert_called()
    first_call_args = mock_channel.send.call_args[0][0]
    assert "의도를 파악하고 있습니다" in first_call_args


@pytest.mark.asyncio
async def test_handle_dm_registers_user_and_calls_stream():
    """DM 수신 시 사용자 등록 후 스트리밍 함수를 호출하는지 검증."""
    from panager.discord.handlers import handle_dm

    mock_message = MagicMock()
    mock_message.author.id = 123
    mock_message.author.__str__ = MagicMock(return_value="test_user#1234")
    mock_message.channel = AsyncMock()
    mock_message.content = "hello"

    mock_graph = MagicMock()

    # DB Mock
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

        # 유저 정보 저장 쿼리 확인
        mock_conn.execute.assert_awaited()
        # 스트리밍 함수 호출 확인
        mock_stream.assert_awaited_once()
