import pytest
from unittest.mock import patch
from langchain_core.messages import AIMessage, ToolMessage

from panager import agent
from panager.agent.graph import _hitl_node, _should_continue_or_hitl
from panager.agent.state import AgentState


@pytest.mark.asyncio
async def test_hitl_node_approved_returns_tool_call():
    """interrupt가 approved를 반환하면 hitl_tool_call이 설정되는지 검증."""
    tool_call = {"name": "task_delete", "args": {"task_id": "abc"}, "id": "call_1"}
    state: AgentState = {  # type: ignore[typeddict-item]
        "user_id": 123,
        "username": "testuser",
        "messages": [AIMessage(content="", tool_calls=[tool_call])],
        "memory_context": "",
    }

    with patch.object(agent.graph, "interrupt", return_value="approved"):
        result = await _hitl_node(state)

    assert result.get("hitl_tool_call", {}).get("name") == tool_call["name"]
    assert result.get("hitl_tool_call", {}).get("id") == tool_call["id"]
    assert "messages" not in result or result.get("messages") == []


@pytest.mark.asyncio
async def test_hitl_node_rejected_returns_cancel_message():
    """interrupt가 rejected를 반환하면 취소 ToolMessage가 반환되는지 검증."""
    tool_call = {"name": "task_delete", "args": {"task_id": "abc"}, "id": "call_1"}
    state: AgentState = {  # type: ignore[typeddict-item]
        "user_id": 123,
        "username": "testuser",
        "messages": [AIMessage(content="", tool_calls=[tool_call])],
        "memory_context": "",
    }

    with patch.object(agent.graph, "interrupt", return_value="rejected"):
        result = await _hitl_node(state)

    msgs = result.get("messages", [])
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    assert "취소" in msgs[0].content
    assert result.get("hitl_tool_call") is None


@pytest.mark.asyncio
async def test_should_continue_or_hitl_routes_hitl_tools():
    """HITL 대상 tool_call이 있을 때 'hitl'로 라우팅되는지 검증."""
    tool_call = {"name": "task_delete", "args": {}, "id": "c1"}
    state: AgentState = {  # type: ignore[typeddict-item]
        "user_id": 1,
        "username": "u",
        "messages": [AIMessage(content="", tool_calls=[tool_call])],
        "memory_context": "",
    }
    assert _should_continue_or_hitl(state) == "hitl"


@pytest.mark.asyncio
async def test_should_continue_or_hitl_routes_normal_tools():
    """일반 tool_call은 'tools'로 라우팅되는지 검증."""
    tool_call = {"name": "memory_save", "args": {}, "id": "c2"}
    state: AgentState = {  # type: ignore[typeddict-item]
        "user_id": 1,
        "username": "u",
        "messages": [AIMessage(content="", tool_calls=[tool_call])],
        "memory_context": "",
    }
    assert _should_continue_or_hitl(state) == "tools"
