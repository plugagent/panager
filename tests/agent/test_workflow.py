import pytest
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.llm_model = "test-model"
    settings.llm_base_url = "http://test"
    settings.llm_api_key = "test-key"
    settings.checkpoint_max_tokens = 4000
    return settings


@pytest.fixture
def mock_services():
    return {
        "session_provider": MagicMock(),
        "memory_service": MagicMock(),
        "google_service": MagicMock(),
        "github_service": MagicMock(),
        "notion_service": MagicMock(),
        "scheduler_service": MagicMock(),
        "registry": MagicMock(),
    }


@pytest.mark.asyncio
async def test_graph_builds_successfully(mock_services, mock_settings):
    from panager.agent.workflow import build_graph

    with patch("panager.agent.workflow.Settings", return_value=mock_settings):
        graph = build_graph(
            MemorySaver(),
            mock_services["session_provider"],
            mock_services["memory_service"],
            mock_services["google_service"],
            mock_services["github_service"],
            mock_services["notion_service"],
            mock_services["scheduler_service"],
            mock_services["registry"],
        )
        assert graph is not None


@pytest.mark.asyncio
async def test_graph_processes_message(mock_services, mock_settings):
    from langchain_core.messages import AIMessage

    mock_llm_response = AIMessage(content="안녕하세요!")

    with (
        patch("panager.agent.supervisor.get_llm") as mock_get_llm,
        patch("panager.agent.workflow.Settings", return_value=mock_settings),
    ):
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_get_llm.return_value = mock_llm

        from panager.agent.workflow import build_graph

        graph = build_graph(
            MemorySaver(),
            mock_services["session_provider"],
            mock_services["memory_service"],
            mock_services["google_service"],
            mock_services["github_service"],
            mock_services["notion_service"],
            mock_services["scheduler_service"],
            mock_services["registry"],
        )
        assert graph is not None


@pytest.mark.asyncio
async def test_agent_node_system_prompt_contains_date_and_timezone(
    mock_services, mock_settings
):
    """supervisor_node가 system prompt에 현재 연도와 timezone을 포함하는지 검증."""
    from datetime import datetime
    import zoneinfo

    captured_messages = []
    mock_llm_response = AIMessage(content='{"next_worker": "FINISH"}')

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return mock_llm_response

    with (
        patch("panager.agent.supervisor.get_llm") as mock_get_llm,
    ):
        mock_llm = MagicMock()
        mock_llm.ainvoke = fake_ainvoke
        mock_get_llm.return_value = mock_llm

        from panager.agent.supervisor import supervisor_node
        from panager.agent.state import AgentState

        state = cast(
            AgentState,
            {
                "user_id": 1,
                "username": "테스트유저",
                "messages": [HumanMessage(content="안녕")],
                "memory_context": "없음",
                "timezone": "Asia/Seoul",
            },
        )
        await supervisor_node(
            state,
            mock_settings,
            mock_services["session_provider"],
        )

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
async def test_agent_node_invalid_timezone_falls_back_to_seoul(
    mock_services, mock_settings
):
    """유효하지 않은 timezone이 주어졌을 때 Asia/Seoul로 폴백하는지 검증."""

    captured_messages = []
    mock_llm_response = AIMessage(content='{"next_worker": "FINISH"}')

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return mock_llm_response

    with (
        patch("panager.agent.supervisor.get_llm") as mock_get_llm,
    ):
        mock_llm = MagicMock()
        mock_llm.ainvoke = fake_ainvoke
        mock_get_llm.return_value = mock_llm

        from panager.agent.supervisor import supervisor_node
        from panager.agent.state import AgentState

        state = cast(
            AgentState,
            {
                "user_id": 1,
                "username": "테스트유저",
                "messages": [HumanMessage(content="안녕")],
                "memory_context": "없음",
                "timezone": "Invalid/Timezone_XYZ",
            },
        )
        # Should not raise ZoneInfoNotFoundError
        await supervisor_node(
            state,
            mock_settings,
            mock_services["session_provider"],
        )

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
async def test_agent_node_calls_trim_messages_with_correct_args(
    mock_services, mock_settings
):
    """supervisor_node가 trim_messages를 올바른 인자로 호출하는지 검증."""
    from panager.agent.supervisor import supervisor_node

    mock_llm_response = AIMessage(content='{"next_worker": "FINISH"}')
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    from panager.agent.state import AgentState

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "messages": [HumanMessage(content="안녕")],
            "memory_context": "",
            "timezone": "Asia/Seoul",
        },
    )

    with (
        patch("panager.agent.supervisor.get_llm", return_value=mock_llm),
        patch("panager.agent.supervisor.trim_agent_messages") as mock_trim,
    ):
        mock_trim.return_value = state["messages"]
        await supervisor_node(
            state,
            mock_settings,
            mock_services["session_provider"],
        )

    mock_trim.assert_called_once()
    _, call_kwargs = mock_trim.call_args
    assert call_kwargs["max_tokens"] == mock_settings.checkpoint_max_tokens


@pytest.mark.asyncio
async def test_agent_node_system_trigger_adds_instruction(mock_services, mock_settings):
    """is_system_trigger가 True일 때 시스템 프롬프트에 지시어가 추가되는지 검증."""
    from panager.agent.supervisor import supervisor_node

    captured_messages = []
    mock_llm_response = AIMessage(content='{"next_worker": "FINISH"}')

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return mock_llm_response

    with (
        patch("panager.agent.supervisor.get_llm") as mock_get_llm,
    ):
        mock_llm = MagicMock()
        mock_llm.ainvoke = fake_ainvoke
        mock_get_llm.return_value = mock_llm

        from panager.agent.state import AgentState

        state = cast(
            AgentState,
            {
                "user_id": 1,
                "username": "테스트유저",
                "messages": [HumanMessage(content="예약된 작업 실행")],
                "memory_context": "없음",
                "timezone": "Asia/Seoul",
                "is_system_trigger": True,
            },
        )
        await supervisor_node(
            state,
            mock_settings,
            mock_services["session_provider"],
        )

    assert len(captured_messages) >= 1
    system_msg = captured_messages[0]
    assert isinstance(system_msg, SystemMessage)
    assert "과거에 예약된 작업입니다" in system_msg.content


@pytest.mark.asyncio
async def test_agent_node_strips_scheduled_event_prefix(mock_services, mock_settings):
    """메시지에 포함된 [SCHEDULED_EVENT] 접두사가 제거되는지 검증."""
    from panager.agent.supervisor import supervisor_node

    mock_llm_response = AIMessage(content='{"next_worker": "FINISH"}')
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    with (
        patch("panager.agent.supervisor.get_llm", return_value=mock_llm),
    ):
        from panager.agent.state import AgentState

        state = cast(
            AgentState,
            {
                "user_id": 1,
                "username": "테스트유저",
                "messages": [
                    HumanMessage(content="[SCHEDULED_EVENT] 내일 일정 알려줘")
                ],
                "memory_context": "없음",
                "timezone": "Asia/Seoul",
                "is_system_trigger": False,
            },
        )
        await supervisor_node(
            state,
            mock_settings,
            mock_services["session_provider"],
        )

    # state["messages"][-1] should be cleaned
    assert state["messages"][-1].content == "내일 일정 알려줘"
