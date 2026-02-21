# 기능 추가: 반복 이벤트 생성 + 할 일 삭제 + Human in the Loop

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Google Calendar 반복 이벤트 생성, Google Tasks 할 일 삭제, LangGraph interrupt() 기반 HITL(Human in the Loop) 확인 기능을 추가한다.

**Architecture:**
- `make_recurring_event_create`: 기존 calendar tool 패턴을 따르는 새 factory. Calendar API `recurrence` 필드에 RRULE 문자열을 전달.
- `make_task_delete`: 기존 task tool 패턴을 따르는 새 factory. Tasks API `delete()` 호출.
- HITL: `_should_continue_or_hitl` 조건 분기 → `_hitl_node`(interrupt()) → Discord 버튼(ConfirmView) → `on_interaction` → `Command(resume=...)` 재개.

**Tech Stack:** Python 3.13, asyncio, discord.py, LangGraph (`interrupt`, `Command`), pytest-asyncio

**HITL 대상 tool:** `schedule_create`, `recurring_event_create`, `task_delete`

**HITL 거절 시:** "취소되었습니다." ToolMessage → agent_node 재호출 (대안 제안)

---

### Task 1: 할 일 삭제 — `make_task_delete`

**Files:**
- Modify: `src/panager/google/tasks/tool.py`
- Modify: `src/panager/agent/graph.py`
- Create: `tests/google/tasks/test_task_delete.py`

**Step 1: 실패할 테스트 작성**

`tests/google/tasks/test_task_delete.py` 신규 생성:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_task_delete_tool():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.tasks.return_value.delete.return_value = MagicMock()

    with (
        patch(
            "panager.google.tasks.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
        patch("panager.google.tasks.tool._build_service", return_value=mock_service),
        patch(
            "panager.google.tasks.tool._execute",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        from panager.google.tasks.tool import make_task_delete

        tool = make_task_delete(user_id=123)
        result = await tool.ainvoke({"task_id": "abc123"})

    assert "삭제" in result
    mock_service.tasks.return_value.delete.assert_called_once_with(
        tasklist="@default", task="abc123"
    )
```

**Step 2: 실패 확인**

```bash
uv run pytest tests/google/tasks/test_task_delete.py -v
```

Expected: FAIL — `make_task_delete` 미존재

**Step 3: `tasks/tool.py`에 구현 추가**

기존 `make_task_complete` 아래에 추가:

```python
class TaskDeleteInput(BaseModel):
    task_id: str


def make_task_delete(user_id: int) -> Any:
    @tool(args_schema=TaskDeleteInput)
    async def task_delete(task_id: str) -> str:
        """Google Tasks의 할 일을 삭제합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_service(creds)
        await _execute(service.tasks().delete(tasklist="@default", task=task_id))
        return f"할 일이 삭제되었습니다: {task_id}"

    return task_delete
```

파일 상단에 `from typing import Any` 가 없으면 추가. (기존에 없음 — 추가 필요)

**Step 4: `graph.py` `_build_tools()`에 등록**

```python
from panager.google.tasks.tool import (
    make_task_complete,
    make_task_create,
    make_task_delete,   # 추가
    make_task_list,
)
```

return 리스트에 추가:
```python
make_task_delete(user_id),
```

**Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/google/tasks/ -v
```

Expected: 2 passed (기존 1 + 신규 1)

**Step 6: 전체 테스트**

```bash
uv run pytest tests/agent/ tests/bot/ tests/google/ tests/memory/test_tool.py tests/scheduler/test_tool.py tests/test_config.py tests/test_logging.py -v
```

Expected: 25 passed

**Step 7: 커밋**

```bash
git add src/panager/google/tasks/tool.py src/panager/agent/graph.py tests/google/tasks/test_task_delete.py
git commit -m "feat: 할 일 삭제 툴 추가 (make_task_delete)"
```

---

### Task 2: 반복 이벤트 생성 — `make_recurring_event_create`

**Files:**
- Modify: `src/panager/google/calendar/tool.py`
- Modify: `src/panager/agent/graph.py`
- Create: `tests/google/calendar/test_recurring_event.py`

**Step 1: 실패할 테스트 작성**

`tests/google/calendar/test_recurring_event.py` 신규 생성:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_recurring_event_create():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_created = {"summary": "주간 회의", "id": "evt_abc"}

    with (
        patch(
            "panager.google.calendar.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
        patch(
            "panager.google.calendar.tool._build_service", return_value=mock_service
        ),
        patch(
            "panager.google.calendar.tool._execute",
            new_callable=AsyncMock,
            return_value=mock_created,
        ),
    ):
        from panager.google.calendar.tool import make_recurring_event_create

        tool = make_recurring_event_create(user_id=123)
        result = await tool.ainvoke(
            {
                "title": "주간 회의",
                "start_at": "2026-02-23T10:00:00+09:00",
                "end_at": "2026-02-23T11:00:00+09:00",
                "rrule": "RRULE:FREQ=WEEKLY;BYDAY=MO",
            }
        )

    assert "주간 회의" in result
    call_kwargs = mock_service.events.return_value.insert.call_args.kwargs
    assert "RRULE:FREQ=WEEKLY;BYDAY=MO" in call_kwargs["body"]["recurrence"][0]


@pytest.mark.asyncio
async def test_recurring_event_create_with_description():
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_created = {"summary": "데일리 스탠드업", "id": "evt_xyz"}

    with (
        patch(
            "panager.google.calendar.tool._get_valid_credentials",
            new_callable=AsyncMock,
            return_value=mock_creds,
        ),
        patch(
            "panager.google.calendar.tool._build_service", return_value=mock_service
        ),
        patch(
            "panager.google.calendar.tool._execute",
            new_callable=AsyncMock,
            return_value=mock_created,
        ),
    ):
        from panager.google.calendar.tool import make_recurring_event_create

        tool = make_recurring_event_create(user_id=123)
        result = await tool.ainvoke(
            {
                "title": "데일리 스탠드업",
                "start_at": "2026-02-23T09:00:00+09:00",
                "end_at": "2026-02-23T09:15:00+09:00",
                "rrule": "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
                "description": "팀 데일리 미팅",
            }
        )

    assert "데일리 스탠드업" in result
    call_kwargs = mock_service.events.return_value.insert.call_args.kwargs
    assert call_kwargs["body"].get("description") == "팀 데일리 미팅"
```

**Step 2: 실패 확인**

```bash
uv run pytest tests/google/calendar/test_recurring_event.py -v
```

Expected: FAIL — `make_recurring_event_create` 미존재

**Step 3: `calendar/tool.py`에 구현 추가**

기존 `make_event_delete` 아래에 추가:

```python
class RecurringEventCreateInput(BaseModel):
    title: str
    start_at: str           # ISO 8601, e.g. "2026-02-23T10:00:00+09:00"
    end_at: str             # ISO 8601
    rrule: str              # RFC 5545 RRULE, e.g. "RRULE:FREQ=WEEKLY;BYDAY=MO"
    calendar_id: str = "primary"
    description: str | None = None


def make_recurring_event_create(user_id: int) -> Any:
    @tool(args_schema=RecurringEventCreateInput)
    async def recurring_event_create(
        title: str,
        start_at: str,
        end_at: str,
        rrule: str,
        calendar_id: str = "primary",
        description: str | None = None,
    ) -> str:
        """Google Calendar에 반복 이벤트를 추가합니다. rrule은 RFC 5545 RRULE 형식입니다.
        예: RRULE:FREQ=DAILY, RRULE:FREQ=WEEKLY;BYDAY=MO, RRULE:FREQ=MONTHLY;BYMONTHDAY=1"""
        creds = await _get_valid_credentials(user_id)
        service = _build_service(creds)
        body: dict = {
            "summary": title,
            "start": {"dateTime": start_at},
            "end": {"dateTime": end_at},
            "recurrence": [rrule],
        }
        if description:
            body["description"] = description
        created = await _execute(
            service.events().insert(calendarId=calendar_id, body=body)
        )
        if created is None:
            return "반복 이벤트 추가에 실패했습니다."
        return f"반복 이벤트가 추가되었습니다: {created.get('summary')} (id={created.get('id')})"

    return recurring_event_create
```

**Step 4: `graph.py` 등록 + 시스템 프롬프트 RRULE 가이드 추가**

`_build_tools()` import 및 return:

```python
from panager.google.calendar.tool import (
    make_event_create,
    make_event_delete,
    make_event_list,
    make_event_update,
    make_recurring_event_create,   # 추가
)

# return 리스트에 추가
make_recurring_event_create(user_id),
```

`_agent_node()` 내 `system_prompt` 문자열 끝부분에 RRULE 가이드 추가:

```python
system_prompt = (
    f"당신은 {state['username']}의 개인 매니저 패니저입니다. "
    "사용자의 할 일, 일정, 메모리를 관리하고 적극적으로 도와주세요.\n\n"
    f"현재 날짜/시간: {now_str} ({tz_name})\n"
    "날짜/시간 관련 요청은 반드시 위 현재 시각 기준으로 ISO 8601 형식으로 변환하세요. "
    f"예: {now.strftime('%Y')}-MM-DDTHH:MM:SS{utc_offset}\n\n"
    "반복 이벤트 생성 시 rrule 형식 예시:\n"
    "  매일: RRULE:FREQ=DAILY\n"
    "  매주 월요일: RRULE:FREQ=WEEKLY;BYDAY=MO\n"
    "  매월 1일: RRULE:FREQ=MONTHLY;BYMONTHDAY=1\n"
    "  평일 매일: RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR\n\n"
    f"관련 메모리:\n{state.get('memory_context', '없음')}"
)
```

**Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/google/calendar/ -v
```

Expected: 8 passed (기존 6 + 신규 2)

**Step 6: 전체 테스트**

```bash
uv run pytest tests/agent/ tests/bot/ tests/google/ tests/memory/test_tool.py tests/scheduler/test_tool.py tests/test_config.py tests/test_logging.py -v
```

Expected: 27 passed

**Step 7: 커밋**

```bash
git add src/panager/google/calendar/tool.py src/panager/agent/graph.py tests/google/calendar/test_recurring_event.py
git commit -m "feat: 반복 이벤트 생성 툴 추가 (make_recurring_event_create)"
```

---

### Task 3: HITL — Discord 버튼 + LangGraph interrupt

**Files:**
- Create: `src/panager/bot/views.py` — `ConfirmView`, `HITL_TOOL_LABELS`
- Modify: `src/panager/agent/state.py` — `hitl_tool_call` 필드 추가
- Modify: `src/panager/agent/graph.py` — `_hitl_node`, `_should_continue_or_hitl`, 그래프 엣지
- Modify: `src/panager/bot/client.py` — `hitl_queue`, `_process_hitl_queue`, `on_interaction`
- Create: `tests/agent/test_hitl.py`

**Step 1: 실패할 테스트 작성**

`tests/agent/test_hitl.py` 신규 생성:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, ToolMessage


@pytest.mark.asyncio
async def test_hitl_node_approved_returns_tool_call():
    """_hitl_node가 approved 시 hitl_tool_call을 반환하는지 검증."""
    from panager.agent.graph import _hitl_node
    from panager.agent.state import AgentState

    mock_bot = MagicMock()
    mock_user = AsyncMock()
    mock_dm = AsyncMock()
    mock_bot.fetch_user = AsyncMock(return_value=mock_user)
    mock_user.create_dm = AsyncMock(return_value=mock_dm)
    mock_dm.send = AsyncMock()

    tool_call = {"name": "task_delete", "args": {"task_id": "abc"}, "id": "call_1"}
    state: AgentState = {  # type: ignore[typeddict-item]
        "user_id": 123,
        "username": "testuser",
        "messages": [AIMessage(content="", tool_calls=[tool_call])],
        "memory_context": "",
    }

    with patch("panager.agent.graph.interrupt", return_value="approved"):
        result = await _hitl_node(state, bot=mock_bot)

    assert result.get("hitl_tool_call") == tool_call
    assert "messages" not in result or result.get("messages") == []
    mock_dm.send.assert_called_once()


@pytest.mark.asyncio
async def test_hitl_node_rejected_returns_cancel_message():
    """사용자가 거절 시 취소 ToolMessage가 반환되는지 검증."""
    from panager.agent.graph import _hitl_node
    from panager.agent.state import AgentState

    tool_call = {"name": "task_delete", "args": {"task_id": "abc"}, "id": "call_1"}
    state: AgentState = {  # type: ignore[typeddict-item]
        "user_id": 123,
        "username": "testuser",
        "messages": [AIMessage(content="", tool_calls=[tool_call])],
        "memory_context": "",
    }

    with patch("panager.agent.graph.interrupt", return_value="rejected"):
        result = await _hitl_node(state, bot=None)

    msgs = result.get("messages", [])
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    assert "취소" in msgs[0].content
    assert result.get("hitl_tool_call") is None


@pytest.mark.asyncio
async def test_should_continue_or_hitl_routes_hitl_tools():
    """HITL 대상 tool_call이 있을 때 'hitl'로 라우팅되는지 검증."""
    from panager.agent.graph import _should_continue_or_hitl
    from panager.agent.state import AgentState

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
    from panager.agent.graph import _should_continue_or_hitl
    from panager.agent.state import AgentState

    tool_call = {"name": "memory_save", "args": {}, "id": "c2"}
    state: AgentState = {  # type: ignore[typeddict-item]
        "user_id": 1,
        "username": "u",
        "messages": [AIMessage(content="", tool_calls=[tool_call])],
        "memory_context": "",
    }
    assert _should_continue_or_hitl(state) == "tools"
```

**Step 2: 실패 확인**

```bash
uv run pytest tests/agent/test_hitl.py -v
```

Expected: FAIL — `_hitl_node`, `_should_continue_or_hitl` 미존재

**Step 3: `src/panager/bot/views.py` 신규 생성**

```python
from __future__ import annotations

from typing import Any

import discord

HITL_TOOL_LABELS: dict[str, str] = {
    "schedule_create": "일정 예약",
    "recurring_event_create": "반복 이벤트 생성",
    "task_delete": "할 일 삭제",
}


class ConfirmView(discord.ui.View):
    """HITL 확인 버튼 UI — 5분 타임아웃."""

    def __init__(self, thread_id: str, bot: Any) -> None:
        super().__init__(timeout=300)
        self.thread_id = thread_id
        self.bot = bot

    @discord.ui.button(label="✅ 예", style=discord.ButtonStyle.success)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        self.bot.hitl_queue.put_nowait(
            {"thread_id": self.thread_id, "resume": "approved"}
        )
        self.stop()

    @discord.ui.button(label="❌ 아니오", style=discord.ButtonStyle.danger)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        self.bot.hitl_queue.put_nowait(
            {"thread_id": self.thread_id, "resume": "rejected"}
        )
        self.stop()
```

**Step 4: `agent/state.py` 수정**

`hitl_tool_call` 필드 추가:

```python
from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import NotRequired, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    user_id: int
    username: str
    messages: Annotated[list[BaseMessage], add_messages]
    memory_context: str
    timezone: NotRequired[str]
    hitl_tool_call: NotRequired[dict[str, Any] | None]
```

**Step 5: `agent/graph.py` 수정**

import 추가:
```python
from langgraph.types import interrupt

from panager.bot.views import ConfirmView, HITL_TOOL_LABELS
```

HITL 대상 tool 집합 (모듈 수준):
```python
_HITL_TOOLS: frozenset[str] = frozenset({
    "schedule_create",
    "recurring_event_create",
    "task_delete",
})
```

`_should_continue` → `_should_continue_or_hitl` 으로 교체:
```python
def _should_continue_or_hitl(state: AgentState) -> str:
    if not state["messages"]:
        return END
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return END
    first_tool = last_message.tool_calls[0]["name"]
    if first_tool in _HITL_TOOLS:
        return "hitl"
    return "tools"
```

`_hitl_node` 추가 (`_make_tool_node` 위에):
```python
async def _hitl_node(state: AgentState, bot: Any = None) -> dict:
    """HITL 대상 tool call 전 사용자 확인을 요청하고 interrupt()로 대기한다."""
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[0]  # type: ignore[union-attr]
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]

    # 확인 메시지 구성
    label = HITL_TOOL_LABELS.get(tool_name, tool_name)
    args_text = "\n".join(f"  {k}: {v}" for k, v in tool_args.items())
    confirm_text = (
        f"패니저가 다음 작업을 실행하려 합니다:\n\n"
        f"**{label}**\n{args_text}\n\n"
        "진행하시겠습니까?"
    )

    # Discord 확인 메시지 + 버튼 전송
    if bot is not None:
        user_id = state["user_id"]
        thread_id = str(user_id)
        try:
            user = await bot.fetch_user(user_id)
            dm = await user.create_dm()
            view = ConfirmView(thread_id=thread_id, bot=bot)
            await dm.send(confirm_text, view=view)
        except Exception as exc:
            log.warning("HITL 확인 메시지 전송 실패: %s", exc)

    # 그래프 중단 — 버튼 클릭 시 resume 값으로 재개
    decision = interrupt({"tool_call": tool_call})

    if decision == "approved":
        return {"hitl_tool_call": tool_call}
    else:
        cancel_msg = ToolMessage(
            content="사용자가 작업을 취소했습니다.",
            tool_call_id=tool_call["id"],
        )
        return {"messages": [cancel_msg], "hitl_tool_call": None}
```

`build_graph()` 수정:
```python
def build_graph(checkpointer: Any, bot: Any = None) -> Any:
    graph = StateGraph(AgentState)
    agent_node = functools.partial(_agent_node, bot=bot)
    hitl_node = functools.partial(_hitl_node, bot=bot)

    graph.add_node("agent", agent_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("tools", _make_tool_node(bot))

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        _should_continue_or_hitl,
        {"tools": "tools", "hitl": "hitl", END: END},
    )
    # hitl approved → hitl_tool_call 있음 → tools
    # hitl rejected → hitl_tool_call 없음 → agent (ToolMessage 이미 state에 있음)
    graph.add_conditional_edges(
        "hitl",
        lambda s: "tools" if s.get("hitl_tool_call") else "agent",
    )
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)
```

**Step 6: `bot/client.py` 수정**

import 추가:
```python
from langgraph.types import Command
```

`__init__` 에 추가:
```python
self.hitl_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
```

`setup_hook()` 내 기존 태스크들 아래에 추가:
```python
asyncio.create_task(self._process_hitl_queue())
```

새 메서드 추가:
```python
async def _process_hitl_queue(self) -> None:
    while True:
        event = await self.hitl_queue.get()
        thread_id: str = event["thread_id"]
        resume: str = event["resume"]
        config = {"configurable": {"thread_id": thread_id}}
        try:
            await self.graph.ainvoke(Command(resume=resume), config)
        except Exception as exc:
            log.exception("HITL resume 실패: %s", exc)
```

**Step 7: 테스트 통과 확인**

```bash
uv run pytest tests/agent/test_hitl.py -v
```

Expected: 4 passed

**Step 8: 전체 테스트**

```bash
uv run pytest tests/agent/ tests/bot/ tests/google/ tests/memory/test_tool.py tests/scheduler/test_tool.py tests/test_config.py tests/test_logging.py -v
```

Expected: 31 passed (기존 27 + 신규 4)

**Step 9: 린트**

```bash
uv tool run ruff check src/
```

Expected: `All checks passed!`

**Step 10: 커밋**

```bash
git add src/panager/bot/views.py src/panager/agent/state.py src/panager/agent/graph.py src/panager/bot/client.py tests/agent/test_hitl.py
git commit -m "feat: HITL 구현 — Discord 버튼 확인 후 LangGraph interrupt/resume"
```

---

### Task 4: 전체 테스트 + 린트 + push

**Step 1: 전체 테스트**

```bash
uv run pytest tests/agent/ tests/bot/ tests/google/ tests/memory/test_tool.py tests/scheduler/test_tool.py tests/test_config.py tests/test_logging.py -v
```

**Step 2: 린트**

```bash
uv tool run ruff check src/
```

**Step 3: push**

```bash
git push origin dev
```
