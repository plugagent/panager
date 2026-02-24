# Tool Consolidation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate 12 tools into 4 service-centric tools using Discriminated Unions in Pydantic to improve agent efficiency and reduce token usage.

**Architecture:** Use `Union` of Pydantic models for the `args_schema` of each tool. The `action` field acts as the discriminator. This ensures that the agent provides only relevant parameters for each action.

**Tech Stack:** Python, Pydantic, LangChain, LangGraph.

---

### Task 1: Consolidate Memory Tools

**Files:**
- Modify: `src/panager/agent/tools.py`
- Test: `tests/agent/test_tools.py`

**Step 1: Write the failing test**
Add a test for `internal_memory_service` in `tests/agent/test_tools.py`.

```python
@pytest.mark.asyncio
async def test_internal_memory_service(mock_memory_service):
    user_id = 123
    mock_memory_service.save_memory = AsyncMock()
    mock_memory_service.search_memories = AsyncMock(return_value=["test memory"])

    from panager.agent.tools import make_internal_memory_service
    tool = make_internal_memory_service(user_id, mock_memory_service)
    
    # Test save
    res_save = await tool.ainvoke({"action": "save", "content": "hello"})
    assert json.loads(res_save)["status"] == "success"
    
    # Test search
    res_search = await tool.ainvoke({"action": "search", "query": "hello"})
    assert json.loads(res_search)["status"] == "success"
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/agent/test_tools.py -k test_internal_memory_service`
Expected: FAIL (ImportError or NameError)

**Step 3: Implement `internal_memory_service`**
In `src/panager/agent/tools.py`, define `MemoryAction` (Union) and `make_internal_memory_service`.

```python
class MemorySave(BaseModel):
    action: Literal["save"] = Field(..., description="중요한 내용을 장기 메모리에 저장합니다.")
    content: str

class MemorySearch(BaseModel):
    action: Literal["search"] = Field(..., description="사용자의 과거 대화/패턴에서 관련 내용을 검색합니다.")
    query: str
    limit: int = 5

MemoryAction = Annotated[Union[MemorySave, MemorySearch], Field(discriminator="action")]

def make_internal_memory_service(user_id: int, memory_service: MemoryService) -> BaseTool:
    @tool("internal_memory_service", args_schema=MemoryAction)
    async def internal_memory_service(action: str, **kwargs) -> str:
        """사용자의 메모리를 저장하거나 검색합니다."""
        if action == "save":
            content = kwargs["content"]
            await memory_service.save_memory(user_id, content)
            return json.dumps({"status": "success", "data": {"preview": content[:50]}}, ensure_ascii=False)
        elif action == "search":
            results = await memory_service.search_memories(user_id, kwargs["query"], kwargs.get("limit", 5))
            return json.dumps({"status": "success", "data": {"results": results}}, ensure_ascii=False)
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/agent/test_tools.py -k test_internal_memory_service`
Expected: PASS

**Step 5: Commit**
```bash
git add src/panager/agent/tools.py tests/agent/test_tools.py
git commit -m "feat: internal_memory_service 통합 도구 추가"
```

---

### Task 2: Consolidate Scheduler Tools

**Files:**
- Modify: `src/panager/agent/tools.py`
- Test: `tests/agent/test_tools.py`

**Step 1: Write the failing test**
Add a test for `internal_scheduler_service`.

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/agent/test_tools.py -k test_internal_scheduler_service`

**Step 3: Implement `internal_scheduler_service`**
In `src/panager/agent/tools.py`, define `SchedulerAction` (Union) and `make_internal_scheduler_service`.
- Actions: `create`, `cancel`

**Step 4: Run test to verify it passes**

**Step 5: Commit**
```bash
git add src/panager/agent/tools.py tests/agent/test_tools.py
git commit -m "feat: internal_scheduler_service 통합 도구 추가"
```

---

### Task 3: Consolidate Tasks Tools

**Files:**
- Modify: `src/panager/agent/tools.py`
- Test: `tests/agent/test_tools.py`

**Step 1: Write the failing test**
Add a test for `google_tasks_service`.

**Step 2: Run test to verify it fails**

**Step 3: Implement `google_tasks_service`**
In `src/panager/agent/tools.py`, define `TasksAction` (Union) and `make_google_tasks_service`.
- Actions: `list`, `create`, `update`, `delete`

**Step 4: Run test to verify it passes**

**Step 5: Commit**
```bash
git add src/panager/agent/tools.py tests/agent/test_tools.py
git commit -m "feat: google_tasks_service 통합 도구 추가"
```

---

### Task 4: Consolidate Calendar Tools

**Files:**
- Modify: `src/panager/agent/tools.py`
- Test: `tests/agent/test_tools.py`

**Step 1: Write the failing test**
Add a test for `google_calendar_service`.

**Step 2: Run test to verify it fails**

**Step 3: Implement `google_calendar_service`**
In `src/panager/agent/tools.py`, define `CalendarAction` (Union) and `make_google_calendar_service`.
- Actions: `list`, `create`, `update`, `delete`

**Step 4: Run test to verify it passes**

**Step 5: Commit**
```bash
git add src/panager/agent/tools.py tests/agent/test_tools.py
git commit -m "feat: google_calendar_service 통합 도구 추가"
```

---

### Task 5: Update Workflow and Cleanup

**Files:**
- Modify: `src/panager/agent/workflow.py`
- Modify: `src/panager/agent/tools.py` (remove old tools)
- Test: `tests/agent/test_workflow.py`

**Step 1: Update `workflow.py`**
Replace old `_build_tools` imports and usage with new consolidated tools.
- `make_internal_memory_service`
- `make_internal_scheduler_service`
- `make_google_tasks_service`
- `make_google_calendar_service`

**Step 2: Remove old tool definitions from `tools.py`**
Carefully delete the old `make_...` functions and their input models.

**Step 3: Run all agent tests**
Run: `uv run pytest tests/agent/`
Expected: PASS

**Step 4: Commit**
```bash
git add src/panager/agent/ workflow.py tools.py tests/agent/
git commit -m "refactor: 에이전트 도구 통합 완료 및 기존 도구 제거"
```
