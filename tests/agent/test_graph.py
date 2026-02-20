import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage


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
