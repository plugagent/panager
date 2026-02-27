from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from panager.agent.workflow import (
    auth_interrupt_node,
    discovery_node,
    tool_executor_node,
)
from panager.discord.handlers import ResponseManager, _stream_agent_response


@pytest.mark.asyncio
async def test_auth_interrupt_node_providers():
    """다양한 도메인별 auth_request_url에 대해 올바른 인터럽트가 발생하는지 검증."""
    from langgraph.types import interrupt

    # 1. GitHub
    state = {"auth_request_url": "http://github.com/auth"}
    with patch("panager.agent.workflow.interrupt") as mock_int:
        auth_interrupt_node(state)
        mock_int.assert_called_once()
        assert mock_int.call_args[0][0]["type"] == "github_auth_required"

    # 2. Notion
    state = {"auth_request_url": "http://notion.so/auth"}
    with patch("panager.agent.workflow.interrupt") as mock_int:
        auth_interrupt_node(state)
        assert mock_int.call_args[0][0]["type"] == "notion_auth_required"

    # 3. Google
    state = {"auth_request_url": "http://google.com/auth"}
    with patch("panager.agent.workflow.interrupt") as mock_int:
        auth_interrupt_node(state)
        assert mock_int.call_args[0][0]["type"] == "google_auth_required"


@pytest.mark.asyncio
async def test_discovery_node_empty_cases():
    """메시지가 없거나 비어있는 경우 discovery_node 동작 검증."""
    registry = MagicMock()

    # 메시지 없음
    state = {"messages": []}
    result = await discovery_node(state, registry)
    assert result == {"discovered_tools": []}

    # HumanMessage 아님
    state = {"messages": [AIMessage(content="hi")]}
    result = await discovery_node(state, registry)
    assert result == {"discovered_tools": []}


@pytest.mark.asyncio
async def test_tool_executor_node_tool_not_found():
    """도구를 찾을 수 없는 경우 ToolMessage 응답 검증."""
    registry = MagicMock()
    registry.get_tools_for_user = AsyncMock(return_value=[])  # 도구 없음

    state = {
        "user_id": 1,
        "messages": [
            AIMessage(
                content="", tool_calls=[{"name": "missing", "args": {}, "id": "1"}]
            )
        ],
    }

    result = await tool_executor_node(
        state, registry, MagicMock(), MagicMock(), MagicMock()
    )

    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], ToolMessage)
    assert "not found" in result["messages"][0].content


@pytest.mark.asyncio
async def test_response_manager_render_limit():
    """_render 호출 시 STREAM_DEBOUNCE에 의해 편집이 제한되는지 검증."""
    mock_channel = MagicMock()
    mock_msg = AsyncMock()
    ui = ResponseManager(mock_channel, initial_msg=mock_msg)

    with patch("time.monotonic", side_effect=[1.0, 1.1, 2.0]):
        # 1.0초: 첫 렌더링 (성공)
        await ui.append_text("a")
        assert mock_msg.edit.call_count == 1

        # 1.1초: 데드타임 내 (무시)
        await ui.append_text("b")
        assert mock_msg.edit.call_count == 1

        # 2.0초: 데드타임 경과 (성공)
        await ui.append_text("c")
        assert mock_msg.edit.call_count == 2


@pytest.mark.asyncio
async def test_tool_executor_node_auth_flow():
    """인증 예외 발생 시 각 서비스별 auth_url 획득 로직 검증."""
    from panager.core.exceptions import (
        GoogleAuthRequired,
        GithubAuthRequired,
        NotionAuthRequired,
    )

    registry = MagicMock()
    tool_google = MagicMock()
    tool_google.name = "g"
    tool_google.metadata = {"domain": "google"}
    tool_github = MagicMock()
    tool_github.name = "gh"
    tool_github.metadata = {"domain": "github"}
    tool_notion = MagicMock()
    tool_notion.name = "n"
    tool_notion.metadata = {"domain": "notion"}

    registry.get_tools_for_user = AsyncMock(
        return_value=[tool_google, tool_github, tool_notion]
    )

    google_svc = MagicMock()
    google_svc.get_auth_url.return_value = "google_url"
    github_svc = MagicMock()
    github_svc.get_auth_url.return_value = "github_url"
    notion_svc = MagicMock()
    notion_svc.get_auth_url.return_value = "notion_url"

    # 1. Google Auth
    tool_google.ainvoke.side_effect = GoogleAuthRequired()
    state = {
        "user_id": 1,
        "messages": [
            AIMessage(content="", tool_calls=[{"name": "g", "args": {}, "id": "1"}])
        ],
    }
    res = await tool_executor_node(state, registry, google_svc, github_svc, notion_svc)
    assert res["auth_request_url"] == "google_url"

    # 2. GitHub Auth
    tool_github.ainvoke.side_effect = GithubAuthRequired()
    state = {
        "user_id": 1,
        "messages": [
            AIMessage(content="", tool_calls=[{"name": "gh", "args": {}, "id": "2"}])
        ],
    }
    res = await tool_executor_node(state, registry, google_svc, github_svc, notion_svc)
    assert res["auth_request_url"] == "github_url"

    # 3. Notion Auth
    tool_notion.ainvoke.side_effect = NotionAuthRequired()
    state = {
        "user_id": 1,
        "messages": [
            AIMessage(content="", tool_calls=[{"name": "n", "args": {}, "id": "3"}])
        ],
    }
    res = await tool_executor_node(state, registry, google_svc, github_svc, notion_svc)
    assert res["auth_request_url"] == "notion_url"


@pytest.mark.asyncio
async def test_response_manager_finalize_variants():
    """finalize 시 도메인별 메시지 구성 검증."""
    mock_channel = MagicMock()
    mock_msg = AsyncMock()

    # GitHub
    ui = ResponseManager(mock_channel, initial_msg=mock_msg)
    await ui.finalize(auth_url="http://github.com/login")
    assert "GitHub 인증이 필요합니다" in mock_msg.edit.call_args[1]["content"]

    # Notion
    ui = ResponseManager(mock_channel, initial_msg=mock_msg)
    await ui.finalize(auth_url="http://notion.so/auth")
    assert "Notion 인증이 필요합니다" in mock_msg.edit.call_args[1]["content"]

    # Default (Google)
    ui = ResponseManager(mock_channel, initial_msg=mock_msg)
    await ui.finalize(auth_url="http://google.com/auth")
    assert "Google 인증이 필요합니다" in mock_msg.edit.call_args[1]["content"]
