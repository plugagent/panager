# HITL Refactor: interrupt_before 패턴 구현 플랜

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `hitl_node`의 idempotency 버그(확인 메시지 중복 전송)를 제거하고, Discord 버튼 전송 책임을 `handle_dm`으로 이동하며, 타임아웃 처리를 추가한다.

**Architecture:** `hitl_node`에서 Discord 전송 코드를 제거하고 `interrupt()`만 남긴다. `handle_dm`이 `graph.aget_state`로 interrupt 여부를 감지한 후 Discord 확인 버튼을 전송한다. `_process_hitl_queue`는 resume 후 `_stream_agent_response`로 결과를 Discord에 전달한다. `ConfirmView`에 `on_timeout` 콜백을 추가해 5분 타임아웃 시 자동 거절한다.

**Tech Stack:** Python 3.13, LangGraph, discord.py, asyncio, pytest, uv

---

## Task 1: `_hitl_node` 단순화 — Discord 전송 제거

**Files:**
- Modify: `src/panager/agent/graph.py` (lines 128-168: `_hitl_node` 함수)
- Modify: `src/panager/agent/graph.py` (lines 252-253: `build_graph`의 `hitl_node` 할당)
- Modify: `tests/agent/test_hitl.py` (전체 파일)

### Step 1: 테스트 먼저 작성 (TDD)

테스트 파일 `tests/agent/test_hitl.py`를 아래로 교체:

```python
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
```

### Step 2: 테스트 실행 (FAIL 확인)

```bash
uv run pytest tests/agent/test_hitl.py -v
```

Expected: FAIL — `_hitl_node() missing 1 required positional argument: 'bot'` 또는 `AttributeError: 'NoneType' object has no attribute 'send'`

### Step 3: 구현 변경

`src/panager/agent/graph.py`에서:

1. `_hitl_node` 함수를 아래로 교체:

```python
async def _hitl_node(state: AgentState) -> dict:
    """HITL 대상 tool call 전 interrupt()로 사용자 확인을 대기한다.

    Discord 버튼 전송은 handle_dm에서 담당한다.
    resume 값: "approved" | "rejected"
    """
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[0]  # type: ignore[union-attr]

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

2. `build_graph` 함수에서:
   - `hitl_node = functools.partial(_hitl_node, bot=bot)` 라인 제거
   - `graph.add_node("hitl", hitl_node)` → `graph.add_node("hitl", _hitl_node)` 변경

3. 상단 import에서 `ConfirmView, HITL_TOOL_LABELS` 제거 (사용하지 않음)

### Step 4: 테스트 실행 (PASS 확인)

```bash
uv run pytest tests/agent/test_hitl.py -v
```

Expected: 4개 모두 PASS

### Step 5: 전체 테스트 실행

```bash
uv run pytest tests/agent/ tests/bot/ -v
```

Expected: 전부 PASS

### Step 6: Commit

```bash
git add src/panager/agent/graph.py tests/agent/test_hitl.py
git commit -m "refactor: _hitl_node에서 Discord 전송 제거 — interrupt()만 남김"
```

---

## Task 2: `handle_dm`에서 interrupt 감지 + ConfirmView 전송

**Files:**
- Modify: `src/panager/bot/handlers.py` (`handle_dm` 함수)
- Modify: `tests/bot/test_handlers.py`

### Step 1: 테스트 먼저 작성

`tests/bot/test_handlers.py`에 아래 테스트 2개 추가:

```python
@pytest.mark.asyncio
async def test_handle_dm_ignores_message_during_interrupt():
    """interrupt 대기 중에 새 메시지가 오면 안내 메시지만 보내고 graph를 실행하지 않음."""
    from panager.bot.handlers import handle_dm
    import discord

    mock_bot = MagicMock()
    mock_graph = MagicMock()

    # interrupt 중인 snapshot 모킹
    mock_snapshot = MagicMock()
    mock_snapshot.next = ("hitl",)  # 비어있지 않으면 interrupt 중
    mock_graph.aget_state = AsyncMock(return_value=mock_snapshot)
    mock_graph.astream = MagicMock()  # 호출되면 안 됨

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author.bot = False
    mock_message.author.id = 123
    mock_message.author.__str__ = lambda self: "testuser"
    mock_message.content = "새 메시지"
    mock_message.channel = MagicMock(spec=discord.DMChannel)
    mock_message.channel.send = AsyncMock()

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        )
    )

    with patch("panager.bot.handlers.get_pool", return_value=mock_pool):
        await handle_dm(mock_message, mock_bot, mock_graph)

    mock_graph.astream.assert_not_called()
    mock_message.channel.send.assert_called_once()
    assert "확인" in mock_message.channel.send.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_dm_sends_confirm_view_after_interrupt():
    """astream 후 interrupt가 발생하면 ConfirmView가 전송되는지 검증."""
    from panager.bot.handlers import handle_dm
    import discord
    from langchain_core.messages import AIMessageChunk

    mock_bot = MagicMock()
    mock_graph = MagicMock()

    tool_call = {"name": "task_delete", "args": {"task_id": "abc"}, "id": "call_1"}
    mock_interrupt = MagicMock()
    mock_interrupt.value = {"tool_call": tool_call}

    mock_task = MagicMock()
    mock_task.interrupts = [mock_interrupt]

    snapshot_before = MagicMock()
    snapshot_before.next = ()  # interrupt 없음

    snapshot_after = MagicMock()
    snapshot_after.next = ("hitl",)  # interrupt 발생
    snapshot_after.tasks = [mock_task]

    mock_graph.aget_state = AsyncMock(side_effect=[snapshot_before, snapshot_after])

    async def fake_stream(*args, **kwargs):
        yield (AIMessageChunk(content="처리 중..."), {})

    mock_graph.astream = MagicMock(return_value=fake_stream())

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author.bot = False
    mock_message.author.id = 123
    mock_message.author.__str__ = lambda self: "testuser"
    mock_message.content = "테스트 삭제해줘"
    mock_channel = AsyncMock(spec=discord.DMChannel)
    mock_channel.send = AsyncMock(return_value=AsyncMock())
    mock_message.channel = mock_channel

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        )
    )

    with (
        patch("panager.bot.handlers.get_pool", return_value=mock_pool),
        patch("panager.bot.handlers.ConfirmView") as mock_view_cls,
    ):
        mock_view_cls.return_value = MagicMock()
        await handle_dm(mock_message, mock_bot, mock_graph)

    mock_view_cls.assert_called_once()
    # send가 view와 함께 호출됐는지
    calls = mock_channel.send.call_args_list
    view_call = next((c for c in calls if c.kwargs.get("view") is not None), None)
    assert view_call is not None
```

### Step 2: 테스트 실행 (FAIL 확인)

```bash
uv run pytest tests/bot/test_handlers.py::test_handle_dm_ignores_message_during_interrupt tests/bot/test_handlers.py::test_handle_dm_sends_confirm_view_after_interrupt -v
```

Expected: FAIL — ImportError (ConfirmView import 없음) 또는 AssertionError

### Step 3: 구현 변경

`src/panager/bot/handlers.py`:

1. 상단 import에 추가:
```python
from panager.bot.views import ConfirmView, HITL_TOOL_LABELS
```

2. `handle_dm` 함수를 아래로 교체:

```python
async def handle_dm(message: discord.Message, bot: Any, graph: Any) -> None:
    user_id = message.author.id
    pool = get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username) VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
            str(message.author),
        )

    config = {"configurable": {"thread_id": str(user_id)}}

    # interrupt 대기 중인지 확인
    snapshot = await graph.aget_state(config)
    if snapshot.next:
        await message.channel.send(
            "이전 작업 확인을 기다리고 있어요. 위의 버튼을 눌러주세요."
        )
        return

    state = {
        "user_id": user_id,
        "username": str(message.author),
        "messages": [HumanMessage(content=message.content)],
        "memory_context": "",
        "timezone": "Asia/Seoul",
    }

    await _stream_agent_response(graph, state, config, message.channel)

    # 실행 후 interrupt 발생 여부 확인 (HITL 툴 호출 시)
    snapshot_after = await graph.aget_state(config)
    if snapshot_after.next:
        try:
            tool_call = snapshot_after.tasks[0].interrupts[0].value["tool_call"]
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            label = HITL_TOOL_LABELS.get(tool_name, tool_name)
            args_text = "\n".join(f"  {k}: {v}" for k, v in tool_args.items())
            confirm_text = (
                f"패니저가 다음 작업을 실행하려 합니다:\n\n"
                f"**{label}**\n{args_text}\n\n"
                "진행하시겠습니까?"
            )
            view = ConfirmView(thread_id=str(user_id), bot=bot)
            await message.channel.send(confirm_text, view=view)
        except Exception as exc:
            log.warning("HITL 확인 메시지 전송 실패: %s", exc)
```

### Step 4: 테스트 실행 (PASS 확인)

```bash
uv run pytest tests/bot/test_handlers.py -v
```

Expected: 기존 3개 + 새 2개 = 5개 모두 PASS

### Step 5: Commit

```bash
git add src/panager/bot/handlers.py tests/bot/test_handlers.py
git commit -m "feat: handle_dm에서 interrupt 감지 후 ConfirmView 전송"
```

---

## Task 3: `_process_hitl_queue`에서 resume 후 Discord 응답 전송

**Files:**
- Modify: `src/panager/bot/client.py` (lines 135-169: `_process_hitl_queue` 메서드)
- Modify: `src/panager/bot/handlers.py` (`_stream_agent_response` 시그니처)

### Step 1: `handlers.py` 시그니처 완화

`_stream_agent_response`의 `state` 파라미터가 `dict` 타입인데, resume 시 `Command` 객체를 전달해야 하므로 `Any`로 변경:

```python
async def _stream_agent_response(
    graph: Any,
    state: Any,  # dict (새 실행) 또는 Command (resume)
    config: dict,
    channel: discord.abc.Messageable,
) -> None:
```

### Step 2: `_process_hitl_queue` 수정

`src/panager/bot/client.py`의 `_process_hitl_queue` 메서드를 아래로 교체:

```python
async def _process_hitl_queue(self) -> None:
    from panager.bot.handlers import _stream_agent_response

    while not self._shutdown_event.is_set():
        try:
            event = await asyncio.wait_for(self.hitl_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        thread_id: str = event["thread_id"]
        resume: str = event["resume"]
        config = {"configurable": {"thread_id": thread_id}}
        try:
            user = await self.fetch_user(int(thread_id))
            dm = await user.create_dm()
            await _stream_agent_response(
                self.graph,
                Command(resume=resume),
                config,
                dm,
            )
        except Exception as exc:
            log.exception("HITL resume 실패: %s", exc)
```

### Step 3: 테스트 실행

```bash
uv run pytest tests/agent/ tests/bot/ -v
```

Expected: 전부 PASS

### Step 4: Commit

```bash
git add src/panager/bot/client.py src/panager/bot/handlers.py
git commit -m "fix: HITL resume 후 _stream_agent_response로 Discord 응답 전송"
```

---

## Task 4: `ConfirmView` 타임아웃 처리

**Files:**
- Modify: `src/panager/bot/views.py` (ConfirmView 클래스)

### Step 1: `on_timeout` 메서드 추가

`ConfirmView` 클래스에:

```python
async def on_timeout(self) -> None:
    """5분 타임아웃 시 자동으로 거절 처리."""
    self.bot.hitl_queue.put_nowait(
        {"thread_id": self.thread_id, "resume": "rejected"}
    )
```

### Step 2: 테스트 실행

```bash
uv run pytest tests/agent/ tests/bot/ -v
```

Expected: 전부 PASS

### Step 3: Commit

```bash
git add src/panager/bot/views.py
git commit -m "fix: ConfirmView 타임아웃 시 자동 거절 처리"
```

---

## Task 5: `hitl_tool_call` 상태 초기화

**Files:**
- Modify: `src/panager/agent/graph.py` (lines 171-226: `_tool_node` 함수)

### Step 1: `_tool_node` return 문 수정

현재:
```python
return {"messages": tool_messages}
```

변경:
```python
return {"messages": tool_messages, "hitl_tool_call": None}
```

### Step 2: 테스트 실행

```bash
uv run pytest tests/agent/ tests/bot/ -v
```

Expected: 전부 PASS

### Step 3: Commit

```bash
git add src/panager/agent/graph.py
git commit -m "fix: tool_node 실행 후 hitl_tool_call 상태 초기화"
```

---

## 최종 검증

### Step 1: 전체 테스트 실행

```bash
uv run pytest tests/agent/ tests/bot/ tests/google/ tests/memory/test_tool.py tests/scheduler/test_tool.py tests/test_config.py tests/test_logging.py -v
```

### Step 2: Lint

```bash
uv run ruff check src/panager/agent/graph.py src/panager/bot/handlers.py src/panager/bot/client.py src/panager/bot/views.py
```

### Step 3: 최종 커밋

```bash
git add -A
git commit -m "refactor: HITL interrupt_before 패턴 리팩토링 완료"
```
