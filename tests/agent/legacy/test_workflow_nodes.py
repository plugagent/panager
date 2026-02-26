from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from panager.agent.state import AgentState
from panager.agent.workflow import auth_interrupt_node


@pytest.mark.asyncio
async def test_auth_interrupt_node_google_success():
    """Google 인증 성공 후 이전 워커로 재시도하는지 확인합니다."""
    state: AgentState = {
        "user_id": 123,
        "username": "testuser",
        "memory_context": "",
        "messages": [],
        "auth_request_url": "https://accounts.google.com/o/oauth2/auth?...",
        "next_worker": "GoogleWorker",
    }

    with patch(
        "panager.agent.workflow.interrupt", return_value="auth_success"
    ) as mock_interrupt:
        res = auth_interrupt_node(state)

        mock_interrupt.assert_called_once()
        assert res["next_worker"] == "GoogleWorker"
        assert res["auth_request_url"] is None


@pytest.mark.asyncio
async def test_auth_interrupt_node_github_success_dict():
    """GitHub 인증 성공(dict 형태 응답) 후 이전 워커로 재시도하는지 확인합니다."""
    state: AgentState = {
        "user_id": 123,
        "username": "testuser",
        "memory_context": "",
        "messages": [],
        "auth_request_url": "https://github.com/login/oauth/authorize?...",
        "next_worker": "GithubWorker",
    }

    with patch(
        "panager.agent.workflow.interrupt", return_value={"status": "auth_success"}
    ) as mock_interrupt:
        res = auth_interrupt_node(state)

        mock_interrupt.assert_called_once()
        assert res["next_worker"] == "GithubWorker"
        assert res["auth_request_url"] is None


@pytest.mark.asyncio
async def test_auth_interrupt_node_notion_failure():
    """Notion 인증 실패/취소 시 FINISH로 종료되는지 확인합니다."""
    state: AgentState = {
        "user_id": 123,
        "username": "testuser",
        "memory_context": "",
        "messages": [],
        "auth_request_url": "https://api.notion.com/v1/oauth/authorize?...",
        "next_worker": "NotionWorker",
    }

    with patch("panager.agent.workflow.interrupt", return_value="cancelled"):
        res = auth_interrupt_node(state)

        assert res["next_worker"] == "FINISH"
        assert res["auth_request_url"] is None


@pytest.mark.asyncio
async def test_auth_interrupt_node_none():
    """auth_request_url이 없는 경우 빈 딕셔너리를 반환하는지 확인합니다."""
    state: AgentState = {
        "user_id": 123,
        "username": "testuser",
        "memory_context": "",
        "messages": [],
    }
    res = auth_interrupt_node(state)
    assert res == {}


@pytest.mark.asyncio
async def test_worker_call_wrappers():
    """워커 호출 래퍼들이 AgentState와 WorkerState 간의 변환을 올바르게 수행하는지 확인합니다."""
    from panager.agent.workflow import build_graph
    from langgraph.checkpoint.memory import MemorySaver

    # Mock services
    services = {
        k: MagicMock()
        for k in [
            "session_provider",
            "memory_service",
            "google_service",
            "github_service",
            "notion_service",
            "scheduler_service",
        ]
    }

    # Mock build_..._worker functions to return MagicMocks for the workers
    mock_workers = {
        "google": AsyncMock(),
        "github": AsyncMock(),
        "notion": AsyncMock(),
        "memory": AsyncMock(),
        "scheduler": AsyncMock(),
    }

    with (
        patch(
            "panager.agent.workflow.build_google_worker",
            return_value=mock_workers["google"],
        ),
        patch(
            "panager.agent.workflow.build_github_worker",
            return_value=mock_workers["github"],
        ),
        patch(
            "panager.agent.workflow.build_notion_worker",
            return_value=mock_workers["notion"],
        ),
        patch(
            "panager.agent.workflow.build_memory_worker",
            return_value=mock_workers["memory"],
        ),
        patch(
            "panager.agent.workflow.build_scheduler_worker",
            return_value=mock_workers["scheduler"],
        ),
        patch("panager.agent.workflow.get_llm"),
    ):
        graph = build_graph(MemorySaver(), **services)

        state: AgentState = {
            "user_id": 123,
            "username": "testuser",
            "memory_context": "",
            "messages": [MagicMock(content="test")],
        }

        # Test Google
        google_node = graph.builder.nodes["GoogleWorker"].runnable
        mock_workers["google"].ainvoke.return_value = {
            "messages": state["messages"] + [MagicMock(content="google")],
            "task_summary": "google-done",
            "auth_request_url": "url",
        }
        res_google = await google_node.ainvoke(state)
        assert res_google["task_summary"] == "google-done"

        # Test Notion
        notion_node = graph.builder.nodes["NotionWorker"].runnable
        mock_workers["notion"].ainvoke.return_value = {
            "messages": [],
            "task_summary": "notion-done",
            "pending_reflections": [{"repo": "test"}],
        }
        res_notion = await notion_node.ainvoke(state)
        assert res_notion["pending_reflections"] == [{"repo": "test"}]

        # Test GitHub
        github_node = graph.builder.nodes["GithubWorker"].runnable
        mock_workers["github"].ainvoke.return_value = {
            "messages": [],
            "task_summary": "git",
        }
        await github_node.ainvoke(state)
        mock_workers["github"].ainvoke.assert_called_once()

        # Test Memory
        memory_node = graph.builder.nodes["MemoryWorker"].runnable
        mock_workers["memory"].ainvoke.return_value = {
            "messages": [],
            "task_summary": "mem",
        }
        await memory_node.ainvoke(state)
        mock_workers["memory"].ainvoke.assert_called_once()

        # Test Scheduler
        scheduler_node = graph.builder.nodes["SchedulerWorker"].runnable
        mock_workers["scheduler"].ainvoke.return_value = {
            "messages": [],
            "task_summary": "sched",
        }
        await scheduler_node.ainvoke(state)
        mock_workers["scheduler"].ainvoke.assert_called_once()


def _invoke_branch(func, state):
    if hasattr(func, "invoke"):
        return func.invoke(state)
    return func(state)


@pytest.mark.asyncio
async def test_workflow_routing_logic():
    """그래프의 라우팅 로직을 테스트합니다."""
    from panager.agent.workflow import build_graph
    from langgraph.checkpoint.memory import MemorySaver

    services = {
        k: MagicMock()
        for k in [
            "session_provider",
            "memory_service",
            "google_service",
            "github_service",
            "notion_service",
            "scheduler_service",
        ]
    }
    with (
        patch("panager.agent.workflow.build_google_worker"),
        patch("panager.agent.workflow.build_github_worker"),
        patch("panager.agent.workflow.build_notion_worker"),
        patch("panager.agent.workflow.build_memory_worker"),
        patch("panager.agent.workflow.build_scheduler_worker"),
        patch("panager.agent.workflow.get_llm"),
    ):
        graph = build_graph(MemorySaver(), **services)

        # _route test
        from langgraph.graph import END

        route_func = graph.builder.branches["supervisor"]["_route"].path
        assert _invoke_branch(route_func, {"next_worker": "FINISH"}) == END
        assert _invoke_branch(route_func, {"next_worker": None}) == END
        assert (
            _invoke_branch(route_func, {"next_worker": "GoogleWorker"})
            == "GoogleWorker"
        )

        # _after_auth_worker test
        after_auth_func = graph.builder.branches["GoogleWorker"][
            "_after_auth_worker"
        ].path
        assert (
            _invoke_branch(after_auth_func, {"auth_request_url": "http://auth"})
            == "auth_interrupt"
        )
        assert (
            _invoke_branch(after_auth_func, {"auth_request_url": None}) == "supervisor"
        )
