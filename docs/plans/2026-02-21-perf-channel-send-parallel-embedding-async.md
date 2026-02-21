# 성능 개선: channel.send() 병렬화 + SentenceTransformer 블로킹 수정

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `channel.send()`와 `graph.astream()`을 병렬 실행하여 Discord API 왕복 latency(50–300ms)를 숨기고, `SentenceTransformer` 모델 로드/인코딩의 동기 이벤트 루프 블로킹을 제거한다.

**Architecture:**
- 병목 1: `asyncio.create_task(channel.send(...))` 로 send를 백그라운드에 띄우고 `graph.astream()` 을 즉시 시작. 첫 AI 청크 도착 시 `await send_task` 로 `sent_message` 확보.
- 병목 6: `_get_embedding()` 를 `asyncio.to_thread()` 로 래핑한 `_get_embedding_async()` 로 교체. `setup_hook()` 에서 봇 시작 시 모델 워밍업 태스크 실행.

**Tech Stack:** Python 3.13, asyncio, discord.py, sentence-transformers, pytest-asyncio

---

### Task 1: `_stream_agent_response()` 병렬화

**Files:**
- Modify: `src/panager/bot/handlers.py`
- Modify: `tests/bot/test_handlers.py`

**Step 1: 현재 테스트 통과 확인**

```bash
uv run pytest tests/bot/test_handlers.py -v
```

Expected: 3 passed

**Step 2: `handlers.py` 구현 변경**

`import asyncio` 를 상단에 추가하고, `_stream_agent_response` 를 다음과 같이 전체 교체:

```python
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import discord
from langchain_core.messages import AIMessageChunk, HumanMessage

from panager.db.connection import get_pool

log = logging.getLogger(__name__)

STREAM_DEBOUNCE = 0.2  # seconds — Discord rate limit 대응


async def _stream_agent_response(
    graph: Any,
    state: dict,
    config: dict,
    channel: discord.abc.Messageable,
) -> None:
    """
    LangGraph graph를 스트리밍 모드로 실행하고,
    Discord 채널에 점진적으로 메시지를 전송/수정한다.

    - channel.send()와 graph.astream()을 동시에 시작해 Discord API
      왕복 latency를 LLM 준비 시간과 겹친다.
    - 첫 AI 청크 수신 시 send_task를 await해 sent_message를 확보한다.
    - 200ms 디바운스로 edit() 호출 (rate limit 대응)
    - 스트림 종료 후 커서 제거한 최종 텍스트로 edit()
    """
    # channel.send와 graph.astream을 동시에 시작
    send_task: asyncio.Task[discord.Message] = asyncio.create_task(
        channel.send("생각하는 중...")
    )
    sent_message: discord.Message | None = None
    accumulated = ""
    last_edit_at = 0.0

    async for chunk, _metadata in graph.astream(
        state, config=config, stream_mode="messages"
    ):
        if not isinstance(chunk, AIMessageChunk):
            continue
        if not chunk.content:
            continue
        if not isinstance(chunk.content, str):
            continue

        # 첫 청크 도착 시 send_task 완료 대기 (이미 완료돼 있을 가능성 높음)
        if sent_message is None:
            sent_message = await send_task

        accumulated += chunk.content

        # 디바운스: 마지막 edit 이후 DEBOUNCE 초 이상 경과 시에만 edit
        now = time.monotonic()
        if now - last_edit_at >= STREAM_DEBOUNCE:
            await sent_message.edit(content=accumulated + "▌")
            last_edit_at = now

    # 빈 스트림이거나 send가 아직 완료 안 된 경우 보장
    if sent_message is None:
        sent_message = await send_task

    # 최종 edit: 커서 제거
    final_text = accumulated.strip() or "(응답을 받지 못했습니다.)"
    await sent_message.edit(content=final_text)


async def handle_dm(message: discord.Message, bot: Any, graph: Any) -> None:
    user_id = message.author.id
    pool = get_pool()

    # 신규 사용자 등록 (없으면 INSERT, 있으면 무시)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username) VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
            str(message.author),
        )

    # 에이전트 실행
    config = {"configurable": {"thread_id": str(user_id)}}
    state = {
        "user_id": user_id,
        "username": str(message.author),
        "messages": [HumanMessage(content=message.content)],
        "memory_context": "",
        "timezone": "Asia/Seoul",
    }

    await _stream_agent_response(graph, state, config, message.channel)
```

**Step 3: `tests/bot/test_handlers.py` 수정**

세 번째 테스트의 이름과 주석을 타이밍 순서 가정 없이 수정:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessageChunk


async def _make_fake_stream(*chunks: str):
    """주어진 텍스트 청크들을 yield하는 가짜 astream async generator."""
    for text in chunks:
        yield (AIMessageChunk(content=text), {"thread_id": "test"})


@pytest.mark.asyncio
async def test_stream_builds_message_incrementally():
    """스트리밍 청크가 누적되어 최종 메시지에 반영되는지 검증."""
    from panager.bot.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()
    mock_graph.astream.return_value = _make_fake_stream("안녕", "하세요", "!")

    state = {"user_id": 1, "username": "test", "messages": [], "memory_context": ""}
    config = {"configurable": {"thread_id": "1"}}

    await _stream_agent_response(mock_graph, state, config, mock_channel)

    final_call = sent_message.edit.call_args
    assert final_call is not None
    assert "안녕하세요!" in final_call.kwargs["content"]
    assert "▌" not in final_call.kwargs["content"]


@pytest.mark.asyncio
async def test_stream_empty_response_sends_fallback():
    """LLM이 빈 응답을 반환할 때 fallback 메시지가 전송되는지 검증."""
    from panager.bot.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()
    mock_graph.astream.return_value = _make_fake_stream()

    state = {"user_id": 1, "username": "test", "messages": [], "memory_context": ""}
    config = {"configurable": {"thread_id": "1"}}

    await _stream_agent_response(mock_graph, state, config, mock_channel)

    mock_channel.send.assert_called_once_with("생각하는 중...")
    sent_message.edit.assert_called_once_with(content="(응답을 받지 못했습니다.)")


@pytest.mark.asyncio
async def test_stream_sends_thinking_message():
    """channel.send('생각하는 중...')가 반드시 1회 호출되는지 검증."""
    from panager.bot.handlers import _stream_agent_response

    mock_channel = MagicMock()
    sent_message = AsyncMock()
    sent_message.edit = AsyncMock()
    mock_channel.send = AsyncMock(return_value=sent_message)

    mock_graph = MagicMock()
    mock_graph.astream.return_value = _make_fake_stream("hello")

    state = {"user_id": 1, "username": "test", "messages": [], "memory_context": ""}
    config = {"configurable": {"thread_id": "1"}}

    await _stream_agent_response(mock_graph, state, config, mock_channel)

    # "생각하는 중..." 메시지가 반드시 1회 전송 (타이밍 순서는 무관)
    mock_channel.send.assert_called_once_with("생각하는 중...")
```

**Step 4: 테스트 실행**

```bash
uv run pytest tests/bot/test_handlers.py -v
```

Expected: 3 passed

**Step 5: 전체 테스트 실행**

```bash
uv run pytest tests/agent/ tests/bot/ tests/google/ tests/memory/test_tool.py tests/scheduler/test_tool.py tests/test_config.py tests/test_logging.py -v
```

Expected: 24 passed

**Step 6: 커밋**

```bash
git add src/panager/bot/handlers.py tests/bot/test_handlers.py
git commit -m "perf: channel.send()와 graph.astream() 병렬 실행으로 응답 latency 개선"
```

---

### Task 2: `SentenceTransformer` 블로킹 제거

**Files:**
- Modify: `src/panager/memory/tool.py`
- Modify: `src/panager/bot/client.py`
- Modify: `tests/memory/test_tool.py`

**Step 1: 실패할 테스트 먼저 작성**

`tests/memory/test_tool.py` 를 다음으로 교체. `_get_embedding_async` 를 mock하도록 변경:

```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_memory_save_tool():
    with (
        patch("panager.memory.tool.save_memory", new_callable=AsyncMock) as mock_save,
        patch(
            "panager.memory.tool._get_embedding_async",
            new_callable=AsyncMock,
            return_value=[0.1] * 768,
        ),
    ):
        mock_save.return_value = "test-uuid"

        from panager.memory.tool import make_memory_save

        tool = make_memory_save(user_id=123)
        result = await tool.ainvoke({"content": "오늘 회의 참석"})
        assert "저장" in result
        mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_memory_search_tool():
    with (
        patch(
            "panager.memory.tool.search_memories", new_callable=AsyncMock
        ) as mock_search,
        patch(
            "panager.memory.tool._get_embedding_async",
            new_callable=AsyncMock,
            return_value=[0.1] * 768,
        ),
    ):
        mock_search.return_value = ["오늘 회의 참석"]

        from panager.memory.tool import make_memory_search

        tool = make_memory_search(user_id=123)
        result = await tool.ainvoke({"query": "회의", "limit": 5})
        assert "오늘 회의 참석" in result
```

**Step 2: 테스트 실행해 실패 확인**

```bash
uv run pytest tests/memory/test_tool.py -v
```

Expected: FAIL — `_get_embedding_async` 미존재

**Step 3: `memory/tool.py` 구현 변경**

```python
from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from panager.memory.repository import save_memory, search_memories

_model: SentenceTransformer | None = None


def _get_embedding(text: str) -> list[float]:
    """동기 임베딩 계산 — asyncio.to_thread()를 통해서만 호출할 것."""
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    return _model.encode(text).tolist()


async def _get_embedding_async(text: str) -> list[float]:
    """이벤트 루프를 블로킹하지 않는 비동기 임베딩 계산."""
    return await asyncio.to_thread(_get_embedding, text)


async def _warmup_embedding_model() -> None:
    """봇 시작 시 모델을 미리 로드해 첫 사용 시 cold start를 제거한다."""
    await _get_embedding_async("")


# ---------------------------------------------------------------------------
# Tool factories – user_id는 클로저로 포함, LLM에 노출되지 않음
# ---------------------------------------------------------------------------


class MemorySaveInput(BaseModel):
    content: str


class MemorySearchInput(BaseModel):
    query: str
    limit: int = 5


def make_memory_save(user_id: int) -> Any:
    @tool(args_schema=MemorySaveInput)
    async def memory_save(content: str) -> str:
        """중요한 내용을 장기 메모리에 저장합니다."""
        embedding = await _get_embedding_async(content)
        await save_memory(user_id, content, embedding)
        return f"메모리에 저장했습니다: {content[:50]}"

    return memory_save


def make_memory_search(user_id: int) -> Any:
    @tool(args_schema=MemorySearchInput)
    async def memory_search(query: str, limit: int = 5) -> str:
        """사용자의 과거 대화/패턴에서 관련 내용을 검색합니다."""
        embedding = await _get_embedding_async(query)
        results = await search_memories(user_id, embedding, limit)
        if not results:
            return "관련 메모리가 없습니다."
        return "\n".join(f"- {r}" for r in results)

    return memory_search
```

**Step 4: `bot/client.py` 워밍업 태스크 추가**

`client.py` 상단 import에 추가:
```python
from panager.memory.tool import _warmup_embedding_model
```

`setup_hook()` 내 `log.info("봇 설정 완료")` 바로 위에 추가:
```python
asyncio.create_task(_warmup_embedding_model())
```

**Step 5: 테스트 실행**

```bash
uv run pytest tests/memory/test_tool.py -v
```

Expected: 2 passed

**Step 6: 전체 테스트 실행**

```bash
uv run pytest tests/agent/ tests/bot/ tests/google/ tests/memory/test_tool.py tests/scheduler/test_tool.py tests/test_config.py tests/test_logging.py -v
```

Expected: 24 passed

**Step 7: 린트**

```bash
uv tool run ruff check src/
```

Expected: `All checks passed!`

**Step 8: 커밋**

```bash
git add src/panager/memory/tool.py src/panager/bot/client.py tests/memory/test_tool.py
git commit -m "perf: SentenceTransformer 동기 블로킹 제거 및 봇 시작 시 모델 워밍업"
```

---

### Task 3: push

```bash
git push origin dev
```
