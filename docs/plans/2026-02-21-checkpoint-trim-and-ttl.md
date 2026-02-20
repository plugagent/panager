# Checkpoint Trim & TTL Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** LLM에 전달되는 messages를 최대 토큰 수로 트리밍하고, 오래된 PostgreSQL checkpoint를 TTL 기반으로 자동 삭제한다.

**Architecture:** `trim_messages()` (LangChain 공식 유틸)를 `_agent_node`에서 LLM 호출 전에 적용해 토큰 누적을 방지한다. 봇 시작 시 `setup_hook`에서 TTL 초과 checkpoint를 PostgreSQL에서 삭제한다. 두 설정값(`CHECKPOINT_MAX_TOKENS`, `CHECKPOINT_TTL_DAYS`)은 환경변수로 분리한다.

**Tech Stack:** `langchain-core>=0.3` (`trim_messages`), `psycopg3` (AsyncConnection), `pydantic-settings`

---

### Task 1: 환경변수 추가

**Files:**
- Modify: `src/panager/config.py`
- Modify: `.env.example`

**Step 1: `config.py`에 필드 추가**

`Settings` 클래스에 아래 두 필드를 추가한다:

```python
checkpoint_max_tokens: int = 4000   # LLM에 전달할 messages 최대 토큰 수
checkpoint_ttl_days: int = 30       # checkpoint 보관 기간 (일)
```

**Step 2: `.env.example`에 섹션 추가**

파일 말미에 추가:

```dotenv
# Checkpoint
CHECKPOINT_MAX_TOKENS=4000
CHECKPOINT_TTL_DAYS=30
```

**Step 3: 커밋**

```bash
git add src/panager/config.py .env.example
git commit -m "feat: checkpoint 설정 환경변수 추가 (max_tokens, ttl_days)"
```

---

### Task 2: `_agent_node`에 `trim_messages` 적용

**Files:**
- Modify: `src/panager/agent/graph.py`
- Create: `tests/agent/__init__.py`
- Create: `tests/agent/test_graph.py`

**Step 1: 테스트 파일 작성**

```python
# tests/agent/test_graph.py
import pytest
from langchain_core.messages import HumanMessage, AIMessage


def test_trim_messages_drops_old_messages_when_over_limit():
    """token_counter가 초과될 때 오래된 메시지가 제거되는지 검증."""
    from langchain_core.messages import trim_messages

    messages = []
    for i in range(10):
        messages.append(HumanMessage(content=f"질문 {i} " + "x" * 50))
        messages.append(AIMessage(content=f"답변 {i} " + "x" * 50))

    # 글자 수 기준 단순 token_counter (테스트용)
    def char_counter(msgs):
        return sum(len(m.content) for m in msgs)

    trimmed = trim_messages(
        messages,
        max_tokens=200,
        strategy="last",
        token_counter=char_counter,
        include_system=False,
        allow_partial=False,
        start_on="human",
    )

    assert char_counter(trimmed) <= 200
    assert len(trimmed) < len(messages)
    # 마지막 메시지는 반드시 포함되어야 함
    assert trimmed[-1].content == messages[-1].content


def test_trim_messages_keeps_all_when_under_limit():
    """토큰이 한도 이하일 때 모든 메시지가 유지되는지 검증."""
    from langchain_core.messages import trim_messages

    messages = [
        HumanMessage(content="안녕"),
        AIMessage(content="안녕하세요!"),
    ]

    def char_counter(msgs):
        return sum(len(m.content) for m in msgs)

    trimmed = trim_messages(
        messages,
        max_tokens=10000,
        strategy="last",
        token_counter=char_counter,
        include_system=False,
        allow_partial=False,
        start_on="human",
    )

    assert len(trimmed) == len(messages)
```

**Step 2: 테스트 실행 (PASS 확인)**

```bash
pytest tests/agent/test_graph.py -v
```

Expected: 2 passed

**Step 3: `graph.py` 수정**

`_agent_node` 함수 안, `llm = _get_llm().bind_tools(tools)` 다음에 추가:

```python
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage, trim_messages

# ... _agent_node 안에서 ...
tools = _build_tools(user_id)
llm = _get_llm().bind_tools(tools)

trimmed_messages = trim_messages(
    state["messages"],
    max_tokens=settings.checkpoint_max_tokens,
    strategy="last",
    token_counter=llm,
    include_system=False,
    allow_partial=False,
    start_on="human",
)

messages = [SystemMessage(content=system_prompt)] + trimmed_messages
response = await llm.ainvoke(messages)
```

`settings = _get_settings()` 호출이 함수 상단에 있어야 함 (없으면 추가).

**Step 4: 전체 테스트 실행**

```bash
pytest -v
```

Expected: all pass

**Step 5: 커밋**

```bash
git add src/panager/agent/graph.py tests/agent/
git commit -m "feat: _agent_node에 trim_messages 적용으로 토큰 누적 방지"
```

---

### Task 3: Checkpoint TTL 정리

**Files:**
- Modify: `src/panager/bot/client.py`

**Step 1: `_cleanup_old_checkpoints` 함수 추가 및 `setup_hook` 호출**

`client.py`에 모듈 레벨 헬퍼 함수 추가:

```python
async def _cleanup_old_checkpoints(conn: psycopg.AsyncConnection, ttl_days: int) -> None:
    """TTL 초과 checkpoint 행 삭제."""
    await conn.execute(
        "DELETE FROM checkpoints WHERE thread_ts < NOW() - INTERVAL '1 day' * %s",
        (ttl_days,),
    )
    log.info("오래된 checkpoint 정리 완료 (TTL: %d일)", ttl_days)
```

`setup_hook` 안, `await checkpointer.setup()` 바로 다음에 추가:

```python
await _cleanup_old_checkpoints(self._pg_conn, settings.checkpoint_ttl_days)
```

**Step 2: 커밋**

```bash
git add src/panager/bot/client.py
git commit -m "feat: 봇 시작 시 TTL 초과 checkpoint 자동 정리"
```

---

### Task 4: 전체 검증 및 push

```bash
pytest -v
git push
```
