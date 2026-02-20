import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage


@pytest.mark.asyncio
async def test_graph_builds_successfully():
    from panager.agent.graph import build_graph

    graph = build_graph(MemorySaver())
    assert graph is not None


@pytest.mark.asyncio
async def test_graph_processes_message():
    from langchain_core.messages import AIMessage

    mock_llm_response = AIMessage(content="안녕하세요!")

    with patch("panager.agent.graph._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_get_llm.return_value = mock_llm

        from panager.agent.graph import build_graph

        graph = build_graph(MemorySaver())
        assert graph is not None


@pytest.mark.asyncio
async def test_agent_node_system_prompt_contains_date_and_timezone():
    """_agent_node가 system prompt에 현재 연도와 timezone을 포함하는지 검증."""
    from datetime import datetime
    import zoneinfo
    from langchain_core.messages import AIMessage, SystemMessage

    captured_messages = []
    mock_llm_response = AIMessage(content="테스트 응답")

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return mock_llm_response

    with (
        patch("panager.agent.graph._get_llm") as mock_get_llm,
        patch("panager.agent.graph._build_tools", return_value=[]),
    ):
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = fake_ainvoke
        mock_get_llm.return_value = mock_llm

        from panager.agent.graph import _agent_node

        state = {
            "user_id": 1,
            "username": "테스트유저",
            "messages": [HumanMessage(content="안녕")],
            "memory_context": "없음",
            "timezone": "Asia/Seoul",
        }
        await _agent_node(state)

    assert len(captured_messages) >= 1
    system_msg = captured_messages[0]
    assert isinstance(system_msg, SystemMessage)

    now_kst = datetime.now(zoneinfo.ZoneInfo("Asia/Seoul"))
    current_year = str(now_kst.year)
    assert current_year in system_msg.content, (
        f"system prompt에 현재 연도 {current_year}가 없음: {system_msg.content[:200]}"
    )
    assert "Asia/Seoul" in system_msg.content


@pytest.mark.asyncio
async def test_agent_node_invalid_timezone_falls_back_to_seoul():
    """유효하지 않은 timezone이 주어졌을 때 Asia/Seoul로 폴백하는지 검증."""
    from datetime import datetime
    import zoneinfo
    from langchain_core.messages import AIMessage, SystemMessage

    captured_messages = []
    mock_llm_response = AIMessage(content="폴백 테스트")

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return mock_llm_response

    with (
        patch("panager.agent.graph._get_llm") as mock_get_llm,
        patch("panager.agent.graph._build_tools", return_value=[]),
    ):
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = fake_ainvoke
        mock_get_llm.return_value = mock_llm

        from panager.agent.graph import _agent_node

        state = {
            "user_id": 1,
            "username": "테스트유저",
            "messages": [HumanMessage(content="안녕")],
            "memory_context": "없음",
            "timezone": "Invalid/Timezone_XYZ",
        }
        # Should not raise ZoneInfoNotFoundError
        await _agent_node(state)

    assert len(captured_messages) >= 1
    system_msg = captured_messages[0]
    assert isinstance(system_msg, SystemMessage)
    # Falls back to Asia/Seoul
    assert "Asia/Seoul" in system_msg.content


def test_trim_messages_drops_old_messages_when_over_limit():
    """token_counter가 초과될 때 오래된 메시지가 제거되는지 검증."""
    from langchain_core.messages import trim_messages

    messages = []
    for i in range(10):
        messages.append(HumanMessage(content=f"질문 {i} " + "x" * 50))
        messages.append(AIMessage(content=f"답변 {i} " + "x" * 50))

    # 글자 수 기준 단순 token_counter (테스트용)
    def char_counter(msgs):
        return sum(len(m.content) for m in msgs)

    trimmed = trim_messages(
        messages,
        max_tokens=200,
        strategy="last",
        token_counter=char_counter,
        include_system=False,
        allow_partial=False,
        start_on="human",
    )

    assert char_counter(trimmed) <= 200
    assert len(trimmed) < len(messages)
    # 마지막 메시지는 반드시 포함되어야 함
    assert trimmed[-1].content == messages[-1].content


def test_trim_messages_keeps_all_when_under_limit():
    """토큰이 한도 이하일 때 모든 메시지가 유지되는지 검증."""
    from langchain_core.messages import trim_messages

    messages = [
        HumanMessage(content="안녕"),
        AIMessage(content="안녕하세요!"),
    ]

    def char_counter(msgs):
        return sum(len(m.content) for m in msgs)

    trimmed = trim_messages(
        messages,
        max_tokens=10000,
        strategy="last",
        token_counter=char_counter,
        include_system=False,
        allow_partial=False,
        start_on="human",
    )

    assert len(trimmed) == len(messages)


@pytest.mark.asyncio
async def test_agent_node_calls_trim_messages_with_correct_args():
    """_agent_node가 trim_messages를 올바른 인자로 호출하는지 검증."""
    from panager.agent.graph import _agent_node
    from panager.config import Settings

    mock_response = AIMessage(content="안녕하세요!")
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    state = {
        "user_id": 123,
        "username": "testuser",
        "messages": [HumanMessage(content="안녕")],
        "memory_context": "",
        "timezone": "Asia/Seoul",
    }

    with (
        patch("panager.agent.graph._get_llm", return_value=mock_llm),
        patch("panager.agent.graph._build_tools", return_value=[]),
        patch("panager.agent.graph.trim_messages") as mock_trim,
    ):
        mock_trim.return_value = state["messages"]
        await _agent_node(state)

    mock_trim.assert_called_once()
    call_kwargs = mock_trim.call_args.kwargs
    settings = Settings()
    assert call_kwargs["max_tokens"] == settings.checkpoint_max_tokens
    assert call_kwargs["strategy"] == "last"
    assert call_kwargs["token_counter"] == "approximate"
