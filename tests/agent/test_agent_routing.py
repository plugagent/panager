from __future__ import annotations

import json
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from panager.agent.state import AgentState, PendingReflection, CommitInfo
from panager.agent.agent import agent_node


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
async def test_agent_node_direct_tool_call(mock_settings, mock_session_provider):
    """에이전트가 직접 도구 호출을 생성하는지 테스트합니다."""
    mock_llm_response = AIMessage(
        content="",
        tool_calls=[{"name": "test_tool", "args": {"q": "test"}, "id": "call_1"}],
    )
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "messages": [HumanMessage(content="테스트 도구 실행해줘")],
            "memory_context": "",
            "timezone": "Asia/Seoul",
        },
    )

    with patch("panager.agent.agent.get_llm", return_value=mock_llm):
        res = await agent_node(state, mock_settings, mock_session_provider)

    assert isinstance(res["messages"][0], AIMessage)
    assert res["messages"][0].tool_calls[0]["name"] == "test_tool"
    # 도구 호출이 있으면 next_worker가 FINISH가 아니어야 함 (혹은 아예 없어야 함)
    assert "next_worker" not in res or res["next_worker"] != "FINISH"


@pytest.mark.asyncio
async def test_agent_node_handling_system_trigger(mock_settings, mock_session_provider):
    """is_system_trigger가 True일 때 시스템 프롬프트에 지시어가 추가되는지 확인합니다."""
    captured_messages = []

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return AIMessage(content="Final response")

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

    with patch("panager.agent.agent.get_llm", return_value=mock_llm):
        await agent_node(state, mock_settings, mock_session_provider)

    system_msg = next(m for m in captured_messages if isinstance(m, SystemMessage))
    assert "automated trigger" in system_msg.content
    assert "과거에 예약된 작업입니다" in system_msg.content


@pytest.mark.asyncio
async def test_agent_node_handling_pending_reflections(
    mock_settings, mock_session_provider
):
    """pending_reflections가 있을 때 시스템 프롬프트에 추가되는지 확인합니다."""
    captured_messages = []

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return AIMessage(content="Final response")

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
                PendingReflection(
                    repository="owner/repo",
                    ref="refs/heads/main",
                    commits=[
                        CommitInfo(
                            message="test commit", timestamp="2023-01-01T00:00:00Z"
                        )
                    ],
                )
            ],
        },
    )

    with patch("panager.agent.agent.get_llm", return_value=mock_llm):
        await agent_node(state, mock_settings, mock_session_provider)

    system_msg = next(m for m in captured_messages if isinstance(m, SystemMessage))
    assert "Pending Reflections" in system_msg.content
    assert "owner/repo" in system_msg.content


@pytest.mark.asyncio
async def test_agent_node_strips_scheduled_event_prefix(
    mock_settings, mock_session_provider
):
    """[SCHEDULED_EVENT] 접두사가 제거되는지 확인합니다."""
    mock_llm_response = AIMessage(content="Final response")
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

    with patch("panager.agent.agent.get_llm", return_value=mock_llm):
        await agent_node(state, mock_settings, mock_session_provider)

    assert state["messages"][-1].content == "Test message"


@pytest.mark.asyncio
async def test_agent_node_message_trimming(mock_settings, mock_session_provider):
    """메시지 트리밍이 수행되는지 확인합니다."""
    mock_llm_response = AIMessage(content="Final response")
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
        patch("panager.agent.agent.get_llm", return_value=mock_llm),
        patch("panager.agent.agent.trim_agent_messages") as mock_trim,
    ):
        mock_trim.return_value = state["messages"]
        await agent_node(state, mock_settings, mock_session_provider)

        mock_trim.assert_called_once()
        assert (
            mock_trim.call_args[1]["max_tokens"] == mock_settings.checkpoint_max_tokens
        )


@pytest.mark.asyncio
async def test_agent_node_invalid_timezone_fallback(
    mock_settings, mock_session_provider
):
    """유효하지 않은 타임존이 주어졌을 때 Asia/Seoul로 폴백하는지 확인합니다."""
    mock_llm_response = AIMessage(content="Final response")
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    state = cast(
        AgentState,
        {
            "user_id": 123,
            "username": "testuser",
            "memory_context": "",
            "messages": [HumanMessage(content="Hello")],
        },
    )

    mock_session_provider.get_user_timezone.return_value = "Invalid/Timezone"

    with patch("panager.agent.agent.get_llm", return_value=mock_llm):
        res = await agent_node(state, mock_settings, mock_session_provider)

    assert res["timezone"] == "Asia/Seoul"


@pytest.mark.asyncio
async def test_agent_node_with_task_summary(mock_settings, mock_session_provider):
    """최근 작업 요약(task_summary)이 있을 때 시스템 메시지에 추가되는지 확인합니다."""
    captured_messages = []

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        return AIMessage(content="Final response")

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

    with patch("panager.agent.agent.get_llm", return_value=mock_llm):
        await agent_node(state, mock_settings, mock_session_provider)

    assert any(
        "Recent tool execution summary: Previous work done" in m.content
        for m in captured_messages
        if isinstance(m, SystemMessage)
    )
