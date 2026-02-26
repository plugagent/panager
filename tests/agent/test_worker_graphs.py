from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from panager.agent.github.graph import build_github_worker
from panager.agent.notion.graph import build_notion_worker
from panager.agent.state import WorkerState
from panager.core.exceptions import GithubAuthRequired, NotionAuthRequired


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    return llm


async def _invoke_node(node, state):
    if hasattr(node, "ainvoke"):
        return await node.ainvoke(state)
    return await node(state)


def _invoke_branch(func, state):
    if hasattr(func, "invoke"):
        return func.invoke(state)
    return func(state)


@pytest.mark.asyncio
async def test_github_worker_agent_node(mock_llm):
    """GitHub 워커의 에이전트 노드가 올바르게 동작하는지 확인합니다."""
    github_service = MagicMock()
    graph = build_github_worker(mock_llm, github_service)
    agent_node = graph.builder.nodes["agent"].runnable

    state: WorkerState = {
        "messages": [],
        "task": "Test GitHub task",
        "main_context": {"user_id": 123},
    }

    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="GitHub 요약"))

    res = await _invoke_node(agent_node, state)

    assert res["task_summary"] == "GitHub 요약"
    assert len(res["messages"]) == 1
    assert isinstance(res["messages"][0], AIMessage)


@pytest.mark.asyncio
async def test_github_worker_tool_node_success(mock_llm):
    """GitHub 워커의 툴 노드 성공 케이스를 테스트합니다."""
    github_service = MagicMock()
    graph = build_github_worker(mock_llm, github_service)
    tool_node = graph.builder.nodes["tools"].runnable

    mock_tool = AsyncMock()
    mock_tool.name = "get_repos"
    mock_tool.ainvoke.return_value = "repo1, repo2"

    state: WorkerState = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "get_repos", "args": {}, "id": "call_1"}],
            )
        ],
        "task": "...",
        "main_context": {"user_id": 123},
    }

    with patch(
        "panager.agent.github.graph.make_github_tools", return_value=[mock_tool]
    ):
        res = await _invoke_node(tool_node, state)

    assert len(res["messages"]) == 1
    assert res["messages"][0].content == "repo1, repo2"


@pytest.mark.asyncio
async def test_github_worker_tool_node_auth_required(mock_llm):
    """GitHub 워커에서 인증 필요 시 auth_request_url을 반환하는지 확인합니다."""
    github_service = MagicMock()
    github_service.get_auth_url.return_value = "http://github-auth"

    graph = build_github_worker(mock_llm, github_service)
    tool_node = graph.builder.nodes["tools"].runnable

    # mock tool
    mock_tool = AsyncMock()
    mock_tool.name = "get_github_repos"
    mock_tool.ainvoke.side_effect = GithubAuthRequired()

    state: WorkerState = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "get_github_repos", "args": {}, "id": "call_1"}],
            )
        ],
        "task": "...",
        "main_context": {"user_id": 123},
    }

    with patch(
        "panager.agent.github.graph.make_github_tools", return_value=[mock_tool]
    ):
        res = await _invoke_node(tool_node, state)

    assert res["auth_request_url"] == "http://github-auth"
    assert len(res["messages"]) == 1
    assert isinstance(res["messages"][0], ToolMessage)
    assert "인증이 필요합니다" in res["messages"][0].content


@pytest.mark.asyncio
async def test_github_worker_should_continue(mock_llm):
    """GitHub 워커의 종료 조건 로직을 테스트합니다."""
    github_service = MagicMock()
    graph = build_github_worker(mock_llm, github_service)
    branch_info = graph.builder.branches["agent"]["_worker_should_continue"]
    should_continue = branch_info.path

    # Cases
    assert (
        _invoke_branch(should_continue, {"messages": [AIMessage(content="done")]})
        == "__end__"
    )
    assert (
        _invoke_branch(
            should_continue,
            {
                "messages": [
                    AIMessage(
                        content="", tool_calls=[{"name": "t", "args": {}, "id": "c"}]
                    )
                ]
            },
        )
        == "tools"
    )
    assert (
        _invoke_branch(should_continue, {"auth_request_url": "url", "messages": []})
        == "__end__"
    )


@pytest.mark.asyncio
async def test_notion_worker_agent_node(mock_llm):
    """Notion 워커의 에이전트 노드를 테스트합니다."""
    notion_service = MagicMock()
    graph = build_notion_worker(mock_llm, notion_service)
    agent_node = graph.builder.nodes["agent"].runnable

    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Notion summary"))
    state: WorkerState = {"messages": [], "task": "t", "main_context": {"user_id": 1}}
    res = await _invoke_node(agent_node, state)
    assert res["task_summary"] == "Notion summary"


@pytest.mark.asyncio
async def test_notion_worker_tool_node_pending_reflections(mock_llm):
    """Notion 워커가 툴 실행 결과에서 pending_reflections를 추출하는지 확인합니다."""
    notion_service = MagicMock()
    graph = build_notion_worker(mock_llm, notion_service)
    tool_node = graph.builder.nodes["tools"].runnable

    mock_tool = AsyncMock()
    mock_tool.name = "save_reflection"
    mock_tool.ainvoke.return_value = json.dumps(
        {"status": "success", "pending_reflections": [{"repo": "remained"}]}
    )

    state: WorkerState = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "save_reflection", "args": {}, "id": "call_2"}],
            )
        ],
        "task": "...",
        "main_context": {"user_id": 123},
    }

    with patch(
        "panager.agent.notion.graph.make_notion_tools", return_value=[mock_tool]
    ):
        res = await _invoke_node(tool_node, state)

    assert res["pending_reflections"] == [{"repo": "remained"}]


@pytest.mark.asyncio
async def test_notion_worker_tool_node_auth_required(mock_llm):
    """Notion 워커에서 인증 필요 시 auth_request_url을 반환하는지 확인합니다."""
    notion_service = MagicMock()
    notion_service.get_auth_url.return_value = "http://notion-auth"

    graph = build_notion_worker(mock_llm, notion_service)
    tool_node = graph.builder.nodes["tools"].runnable

    mock_tool = AsyncMock()
    mock_tool.name = "search_notion"
    mock_tool.ainvoke.side_effect = NotionAuthRequired()

    state: WorkerState = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "search_notion", "args": {}, "id": "call_3"}],
            )
        ],
        "task": "...",
        "main_context": {"user_id": 123},
    }

    with patch(
        "panager.agent.notion.graph.make_notion_tools", return_value=[mock_tool]
    ):
        res = await _invoke_node(tool_node, state)

    assert res["auth_request_url"] == "http://notion-auth"
    assert "인증이 필요합니다" in res["messages"][0].content


@pytest.mark.asyncio
async def test_worker_tool_node_invalid_last_message(mock_llm):
    """툴 노드가 AIMessage가 아닌 메시지를 받았을 때 빈 메시지를 반환하는지 확인합니다."""
    github_service = MagicMock()
    graph = build_github_worker(mock_llm, github_service)
    tool_node = graph.builder.nodes["tools"].runnable

    from langchain_core.messages import HumanMessage

    state: WorkerState = {
        "messages": [HumanMessage(content="Not an AIMessage")],
        "task": "...",
        "main_context": {"user_id": 123},
    }
    res = await _invoke_node(tool_node, state)
    assert res == {"messages": []}


@pytest.mark.asyncio
async def test_notion_worker_tool_node_invalid_json_result(mock_llm):
    """Notion 워커가 툴 실행 결과가 JSON이 아닐 때 안전하게 처리하는지 확인합니다."""
    notion_service = MagicMock()
    graph = build_notion_worker(mock_llm, notion_service)
    tool_node = graph.builder.nodes["tools"].runnable

    mock_tool = AsyncMock()
    mock_tool.name = "save_reflection"
    mock_tool.ainvoke.return_value = "Not a JSON"

    state: WorkerState = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "save_reflection", "args": {}, "id": "call_4"}],
            )
        ],
        "task": "...",
        "main_context": {"user_id": 123},
    }

    with patch(
        "panager.agent.notion.graph.make_notion_tools", return_value=[mock_tool]
    ):
        res = await _invoke_node(tool_node, state)

    assert len(res["messages"]) == 1
    assert res["messages"][0].content == "Not a JSON"
    assert "pending_reflections" not in res


@pytest.mark.asyncio
async def test_notion_worker_tool_node_invalid_last_message(mock_llm):
    """Notion 툴 노드가 AIMessage가 아닌 메시지를 받았을 때 빈 메시지를 반환하는지 확인합니다."""
    notion_service = MagicMock()
    graph = build_notion_worker(mock_llm, notion_service)
    tool_node = graph.builder.nodes["tools"].runnable

    from langchain_core.messages import HumanMessage

    state: WorkerState = {
        "messages": [HumanMessage(content="Not an AIMessage")],
        "task": "...",
        "main_context": {"user_id": 123},
    }
    res = await _invoke_node(tool_node, state)
    assert res == {"messages": []}


@pytest.mark.asyncio
async def test_notion_worker_should_continue(mock_llm):
    """Notion 워커의 종료 조건 로직을 테스트합니다."""
    notion_service = MagicMock()
    graph = build_notion_worker(mock_llm, notion_service)
    branch_info = graph.builder.branches["agent"]["_worker_should_continue"]
    should_continue = branch_info.path

    # Cases
    assert (
        _invoke_branch(should_continue, {"messages": [AIMessage(content="done")]})
        == "__end__"
    )
    assert (
        _invoke_branch(
            should_continue,
            {
                "messages": [
                    AIMessage(
                        content="", tool_calls=[{"name": "t", "args": {}, "id": "c"}]
                    )
                ]
            },
        )
        == "tools"
    )
    assert (
        _invoke_branch(should_continue, {"auth_request_url": "url", "messages": []})
        == "__end__"
    )
