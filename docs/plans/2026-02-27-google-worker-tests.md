# Google Worker Unit Tests Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Achieve near 100% test coverage for `src/panager/agent/google/graph.py` and `src/panager/agent/google/tools.py`.

**Architecture:** Use `pytest-asyncio` for asynchronous tests and `unittest.mock.AsyncMock` to isolate dependencies (LLM, Google Service). The tests are split into graph logic tests and detailed tool logic/validation tests.

**Tech Stack:** Python 3.13, Pytest, LangChain/LangGraph, Pydantic.

---

### Task 1: Initialize Google Worker Graph Tests

**Files:**
- Create: `tests/agent/test_google_worker.py`

**Step 1: Write the initial graph tests**

```python
from __future__ import annotations
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
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
            AIMessage(content="", tool_calls=[{"name": "manage_google_tasks", "args": {}, "id": "c1"}])
        ],
        "task": "...",
        "main_context": {"user_id": 123},
    }
    
    with patch("panager.agent.google.graph.make_manage_google_tasks", return_value=mock_tool), \
         patch("panager.agent.google.graph.make_manage_google_calendar", return_value=mock_tool):
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
            AIMessage(content="", tool_calls=[{"name": "manage_google_tasks", "args": {}, "id": "c1"}])
        ],
        "task": "...",
        "main_context": {"user_id": 123},
    }
    
    with patch("panager.agent.google.graph.make_manage_google_tasks", return_value=mock_tool), \
         patch("panager.agent.google.graph.make_manage_google_calendar", return_value=mock_tool):
        res = await _invoke_node(tool_node, state)
        
    assert res["auth_request_url"] == "http://auth-url"
    assert "인증이 필요합니다" in res["messages"][0].content

@pytest.mark.asyncio
async def test_google_worker_tool_node_invalid_message(mock_llm, mock_google_service):
    graph = build_google_worker(mock_llm, mock_google_service)
    tool_node = graph.builder.nodes["tools"].runnable
    state: WorkerState = {"messages": [HumanMessage(content="hi")], "task": "t", "main_context": {"user_id": 1}}
    res = await _invoke_node(tool_node, state)
    assert res == {"messages": []}

@pytest.mark.asyncio
async def test_google_worker_should_continue(mock_llm, mock_google_service):
    graph = build_google_worker(mock_llm, mock_google_service)
    should_continue = graph.builder.branches["agent"]["_worker_should_continue"].path
    
    assert should_continue({"messages": [AIMessage(content="done")]}) == "__end__"
    assert should_continue({"messages": [AIMessage(content="", tool_calls=[{"name":"t","args":{},"id":"c"}])]}) == "tools"
    assert should_continue({"auth_request_url": "url", "messages": []}) == "__end__"
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/agent/test_google_worker.py -v`

**Step 3: Commit**

```bash
git add tests/agent/test_google_worker.py
git commit -m "test: add unit tests for google worker graph"
```

---

### Task 2: Initialize Google Tools Expansion Tests (Tasks)

**Files:**
- Create: `tests/agent/test_google_tools_expansion.py`

**Step 1: Write Task tool tests including pagination and validation**

```python
from __future__ import annotations
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from panager.agent.google.tools import (
    TaskAction, CalendarAction, 
    make_manage_google_tasks, make_manage_google_calendar
)
from pydantic import ValidationError

@pytest.fixture
def mock_google_service():
    return MagicMock()

@pytest.mark.asyncio
async def test_manage_google_tasks_pagination(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    mock_tasks = mock_service.tasks.return_value
    
    # Mock two pages of results
    mock_tasks.list.return_value.execute.side_effect = [
        {"items": [{"id": "t1"}], "nextPageToken": "token1"},
        {"items": [{"id": "t2"}]}
    ]
    mock_google_service.get_tasks_service = AsyncMock(return_value=mock_service)
    
    tool = make_manage_google_tasks(user_id, mock_google_service)
    result = json.loads(await tool.ainvoke({"action": TaskAction.LIST}))
    
    assert len(result["tasks"]) == 2
    assert mock_tasks.list.call_count == 2

@pytest.mark.asyncio
async def test_manage_google_tasks_validation():
    user_id = 123
    mock_service = MagicMock()
    tool = make_manage_google_tasks(user_id, mock_service)
    
    with pytest.raises(ValidationError):
        await tool.ainvoke({"action": TaskAction.CREATE}) # Missing title
    with pytest.raises(ValidationError):
        await tool.ainvoke({"action": TaskAction.UPDATE_STATUS, "status": "completed"}) # Missing task_id
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/agent/test_google_tools_expansion.py -v`

**Step 3: Commit**

```bash
git add tests/agent/test_google_tools_expansion.py
git commit -m "test: add validation and pagination tests for google tasks tool"
```

---

### Task 3: Complete Google Tools Expansion Tests (Calendar)

**Files:**
- Modify: `tests/agent/test_google_tools_expansion.py`

**Step 1: Add Calendar tool tests including multi-calendar pagination and validation**

```python
@pytest.mark.asyncio
async def test_manage_google_calendar_pagination_and_multi_cal(mock_google_service):
    user_id = 123
    mock_service = MagicMock()
    # 2 calendars
    mock_service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "cal1"}, {"id": "cal2"}]
    }
    mock_events = mock_service.events.return_value
    # Each calendar returns 1 page
    mock_events.list.return_value.execute.side_effect = [
        {"items": [{"id": "e1"}]},
        {"items": [{"id": "e2"}]}
    ]
    mock_google_service.get_calendar_service = AsyncMock(return_value=mock_service)
    
    tool = make_manage_google_calendar(user_id, mock_google_service)
    result = json.loads(await tool.ainvoke({"action": CalendarAction.LIST}))
    
    assert len(result["events"]) == 2
    assert mock_events.list.call_count == 2

@pytest.mark.asyncio
async def test_manage_google_calendar_validation():
    user_id = 123
    mock_service = MagicMock()
    tool = make_manage_google_calendar(user_id, mock_service)
    
    with pytest.raises(ValidationError):
        await tool.ainvoke({"action": CalendarAction.CREATE, "title": "T"}) # Missing dates
    with pytest.raises(ValidationError):
        await tool.ainvoke({"action": CalendarAction.DELETE}) # Missing event_id
```

**Step 2: Run all tests and check coverage**

Run: `uv run pytest tests/agent/test_google_worker.py tests/agent/test_google_tools_expansion.py --cov=src/panager/agent/google`

**Step 3: Commit**

```bash
git add tests/agent/test_google_tools_expansion.py
git commit -m "test: add validation and multi-calendar tests for google calendar tool"
```
