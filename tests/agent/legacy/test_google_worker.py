from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from panager.agent.google.graph import build_google_worker
from panager.agent.state import WorkerState
from panager.core.exceptions import GoogleAuthRequired


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    return llm


@pytest.fixture
def mock_google_service():
    service = MagicMock()
    service.get_auth_url.return_value = "http://auth-url"
    return service


async def _invoke_node(node, state):
    if hasattr(node, "ainvoke"):
        return await node.ainvoke(state)
    return await node(state)


@pytest.mark.asyncio
async def test_google_worker_agent_node(mock_llm, mock_google_service):
    graph = build_google_worker(mock_llm, mock_google_service)
    agent_node = graph.builder.nodes["agent"].runnable

    state: WorkerState = {
        "messages": [],
        "task": "Test task",
        "main_context": {"user_id": 123},
    }

    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Summary"))
    res = await _invoke_node(agent_node, state)

    assert res["task_summary"] == "Summary"
    assert len(res["messages"]) == 1


@pytest.mark.asyncio
async def test_google_worker_tool_node_success(mock_llm, mock_google_service):
    graph = build_google_worker(mock_llm, mock_google_service)
    tool_node = graph.builder.nodes["tools"].runnable

    mock_tool = AsyncMock()
    mock_tool.name = "manage_google_tasks"
    mock_tool.ainvoke.return_value = "Success"

    state: WorkerState = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "manage_google_tasks", "args": {}, "id": "c1"}],
            )
        ],
        "task": "...",
        "main_context": {"user_id": 123},
    }

    with (
        patch(
            "panager.agent.google.graph.make_manage_google_tasks",
            return_value=mock_tool,
        ),
        patch(
            "panager.agent.google.graph.make_manage_google_calendar",
            return_value=mock_tool,
        ),
    ):
        res = await _invoke_node(tool_node, state)

    assert len(res["messages"]) == 1
    assert res["messages"][0].content == "Success"


@pytest.mark.asyncio
async def test_google_worker_tool_node_auth_required(mock_llm, mock_google_service):
    graph = build_google_worker(mock_llm, mock_google_service)
    tool_node = graph.builder.nodes["tools"].runnable

    mock_tool = AsyncMock()
    mock_tool.name = "manage_google_tasks"
    mock_tool.ainvoke.side_effect = GoogleAuthRequired()

    state: WorkerState = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "manage_google_tasks", "args": {}, "id": "c1"}],
            )
        ],
        "task": "...",
        "main_context": {"user_id": 123},
    }

    with (
        patch(
            "panager.agent.google.graph.make_manage_google_tasks",
            return_value=mock_tool,
        ),
        patch(
            "panager.agent.google.graph.make_manage_google_calendar",
            return_value=mock_tool,
        ),
    ):
        res = await _invoke_node(tool_node, state)

    assert res["auth_request_url"] == "http://auth-url"
    assert "인증이 필요합니다" in res["messages"][0].content


@pytest.mark.asyncio
async def test_google_worker_tool_node_invalid_message(mock_llm, mock_google_service):
    graph = build_google_worker(mock_llm, mock_google_service)
    tool_node = graph.builder.nodes["tools"].runnable
    state: WorkerState = {
        "messages": [HumanMessage(content="hi")],
        "task": "t",
        "main_context": {"user_id": 1},
    }
    res = await _invoke_node(tool_node, state)
    assert res == {"messages": []}


def _invoke_branch(func, state):
    if hasattr(func, "invoke"):
        return func.invoke(state)
    return func(state)


@pytest.mark.asyncio
async def test_google_worker_should_continue(mock_llm, mock_google_service):
    graph = build_google_worker(mock_llm, mock_google_service)
    should_continue = graph.builder.branches["agent"]["_worker_should_continue"].path

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
