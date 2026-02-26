from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from panager.agent.state import AgentState
from panager.agent.supervisor import supervisor_node


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.llm_model = "test-model"
    settings.llm_base_url = "http://test"
    settings.llm_api_key = "test-key"
    settings.checkpoint_max_tokens = 4000
    return settings


@pytest.fixture
def mock_session_provider():
    provider = AsyncMock()
    provider.get_user_timezone.return_value = "Asia/Seoul"
    return provider


@pytest.mark.asyncio
async def test_supervisor_node_routing_to_google(mock_settings, mock_session_provider):
    """GoogleWorker로의 라우팅을 테스트합니다."""
    mock_llm_response = AIMessage(content='{"next_worker": "GoogleWorker"}')
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "messages": [HumanMessage(content="내일 일정 추가해줘")],
            "memory_context": "",
            "timezone": "Asia/Seoul",
        },
    )

    with patch("panager.agent.supervisor.get_llm", return_value=mock_llm):
        res = await supervisor_node(state, mock_settings, mock_session_provider)

    assert res["next_worker"] == "GoogleWorker"


@pytest.mark.asyncio
async def test_supervisor_node_handling_system_trigger(
    mock_settings, mock_session_provider
):
    """is_system_trigger가 True일 때 시스템 프롬프트에 지시어가 추가되는지 확인합니다."""
    captured_messages = []

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return AIMessage(content='{"next_worker": "FINISH"}')

    mock_llm = MagicMock()
    mock_llm.ainvoke = fake_ainvoke

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "memory_context": "",
            "messages": [HumanMessage(content="Trigger message")],
            "is_system_trigger": True,
        },
    )

    with patch("panager.agent.supervisor.get_llm", return_value=mock_llm):
        await supervisor_node(state, mock_settings, mock_session_provider)

    system_msg = next(m for m in captured_messages if isinstance(m, SystemMessage))
    assert "automated trigger" in system_msg.content
    assert "과거에 예약된 작업입니다" in system_msg.content


@pytest.mark.asyncio
async def test_supervisor_node_handling_pending_reflections(
    mock_settings, mock_session_provider
):
    """pending_reflections가 있을 때 시스템 프롬프트에 추가되는지 확인합니다."""
    captured_messages = []

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return AIMessage(content='{"next_worker": "FINISH"}')

    mock_llm = MagicMock()
    mock_llm.ainvoke = fake_ainvoke

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "memory_context": "",
            "messages": [HumanMessage(content="Hello")],
            "pending_reflections": [
                {
                    "repository": "owner/repo",
                    "ref": "refs/heads/main",
                    "commits": [1, 2, 3],
                }
            ],
        },
    )

    with patch("panager.agent.supervisor.get_llm", return_value=mock_llm):
        await supervisor_node(state, mock_settings, mock_session_provider)

    system_msg = next(m for m in captured_messages if isinstance(m, SystemMessage))
    assert "Pending Reflections" in system_msg.content
    assert "owner/repo" in system_msg.content


@pytest.mark.asyncio
async def test_supervisor_node_strips_scheduled_event_prefix(
    mock_settings, mock_session_provider
):
    """[SCHEDULED_EVENT] 접두사가 제거되는지 확인합니다."""
    mock_llm_response = AIMessage(content='{"next_worker": "FINISH"}')
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "memory_context": "",
            "messages": [HumanMessage(content="[SCHEDULED_EVENT] Test message")],
        },
    )

    with patch("panager.agent.supervisor.get_llm", return_value=mock_llm):
        await supervisor_node(state, mock_settings, mock_session_provider)

    assert state["messages"][-1].content == "Test message"


@pytest.mark.asyncio
async def test_supervisor_node_message_trimming(mock_settings, mock_session_provider):
    """메시지 트리밍이 수행되는지 확인합니다."""
    mock_llm_response = AIMessage(content='{"next_worker": "FINISH"}')
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "memory_context": "",
            "messages": [HumanMessage(content="Long message" * 100)],
        },
    )

    with (
        patch("panager.agent.supervisor.get_llm", return_value=mock_llm),
        patch("panager.agent.supervisor.trim_agent_messages") as mock_trim,
    ):
        mock_trim.return_value = state["messages"]
        await supervisor_node(state, mock_settings, mock_session_provider)

        mock_trim.assert_called_once()
        assert (
            mock_trim.call_args[1]["max_tokens"] == mock_settings.checkpoint_max_tokens
        )


@pytest.mark.asyncio
async def test_supervisor_node_fallback_on_parse_failure(
    mock_settings, mock_session_provider
):
    """LLM 출력 파싱 실패 시 FINISH로 폴백하는지 확인합니다."""
    mock_llm_response = AIMessage(content="Invalid JSON")
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "memory_context": "",
            "messages": [HumanMessage(content="Hello")],
            "pending_reflections": [
                {
                    "repository": "owner/repo",
                    "ref": "refs/heads/main",
                    "commits": [1, 2, 3],
                }
            ],
        },
    )

    with patch("panager.agent.supervisor.get_llm", return_value=mock_llm):
        res = await supervisor_node(state, mock_settings, mock_session_provider)

    assert res["next_worker"] == "FINISH"


@pytest.mark.asyncio
async def test_supervisor_node_invalid_timezone_fallback(
    mock_settings, mock_session_provider
):
    """유효하지 않은 타임존이 주어졌을 때 Asia/Seoul로 폴백하는지 확인합니다."""
    mock_llm_response = AIMessage(content='{"next_worker": "FINISH"}')
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "memory_context": "",
            "messages": [HumanMessage(content="Hello")],
            # "timezone" is missing
        },
    )

    mock_session_provider.get_user_timezone.return_value = "Invalid/Timezone"

    with patch("panager.agent.supervisor.get_llm", return_value=mock_llm):
        res = await supervisor_node(state, mock_settings, mock_session_provider)

    # No exception raised and default to Asia/Seoul internally
    assert res["timezone"] == "Asia/Seoul"


@pytest.mark.asyncio
async def test_supervisor_node_with_task_summary(mock_settings, mock_session_provider):
    """최근 작업 요약(task_summary)이 있을 때 시스템 메시지에 추가되는지 확인합니다."""
    captured_messages = []

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return AIMessage(content='{"next_worker": "FINISH"}')

    mock_llm = MagicMock()
    mock_llm.ainvoke = fake_ainvoke

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "memory_context": "",
            "messages": [HumanMessage(content="Hello")],
            "task_summary": "Previous work done",
        },
    )

    with patch("panager.agent.supervisor.get_llm", return_value=mock_llm):
        await supervisor_node(state, mock_settings, mock_session_provider)

    assert any(
        "Recent worker activity summary: Previous work done" in m.content
        for m in captured_messages
        if isinstance(m, SystemMessage)
    )
