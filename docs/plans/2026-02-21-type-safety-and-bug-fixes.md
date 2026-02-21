# Type Safety & Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 코드베이스 전반의 Critical 버그, 잠재적 런타임 오류, 타입 어노테이션 미비를 수정한다.

**Architecture:** 기능 변경 없이 안정성 강화에 집중. Critical → Important → Minor 순서로 진행. 각 Task는 독립적이고 커밋 단위로 완결된다.

**Tech Stack:** Python 3.13, pydantic-settings, asyncpg, psycopg3, langchain-core, langgraph, APScheduler, google-auth-oauthlib

---

### Task 1: Critical 버그 수정 — scheduler bot=None & messages 안전성

**Files:**
- Modify: `src/panager/scheduler/tool.py`
- Modify: `src/panager/agent/graph.py`
- Modify: `src/panager/bot/client.py`

**Bug 1 — scheduler bot=None (Critical):**

`scheduler/tool.py:50`에서 APScheduler job에 `args=[None, ...]`을 전달해 알림 발송 시 `AttributeError: 'NoneType' object has no attribute 'fetch_user'`가 발생한다.

수정: `make_schedule_create(user_id: int)` → `make_schedule_create(user_id: int, bot: Any)` 시그니처 변경, closure에서 bot 캡처:

```python
def make_schedule_create(user_id: int, bot: Any):
    @tool(args_schema=ScheduleCreateInput)
    async def schedule_create(message: str, trigger_at: str) -> str:
        ...
        scheduler.add_job(
            send_scheduled_dm,
            "date",
            run_date=trigger_dt,
            args=[bot, user_id, str(schedule_id), message],  # None → bot
            ...
        )
    return schedule_create
```

`agent/graph.py`의 `_build_tools`는 이미 `bot`을 받아 `_make_tool_node`에 전달하고 있으므로, `_build_tools(user_id, bot)` 시그니처에 bot을 추가하고 `make_schedule_create(user_id, bot)` 호출로 변경:

```python
def _build_tools(user_id: int, bot: Any = None) -> list:
    ...
    make_schedule_create(user_id, bot),
```

`_agent_node` 내에서 `_build_tools(user_id)` 호출을 `_build_tools(user_id, bot=bot)` 으로 변경. `_agent_node`는 현재 `bot`을 받지 않으므로, `build_graph`에서 `bot`을 partial/closure로 캡처해 `_agent_node`에 전달하는 방식으로 수정:

```python
# build_graph 안에서
import functools
agent_node = functools.partial(_agent_node, bot=bot)
graph.add_node("agent", agent_node)
```

`_agent_node` 시그니처:
```python
async def _agent_node(state: AgentState, bot: Any = None) -> dict:
    ...
    tools = _build_tools(user_id, bot)
```

**Bug 2 — messages[-1] 빈 리스트 IndexError (Critical):**

`graph.py`의 `_make_tool_node`와 `_should_continue` 둘 다 `state["messages"][-1]` 접근 전 빈 리스트 가드 추가:

```python
# _make_tool_node 안
if not state["messages"]:
    return {"messages": []}
last_message = state["messages"][-1]

# _should_continue 안
if not state["messages"]:
    return END
last_message = state["messages"][-1]
```

**Bug 3 — state["messages"][0] 대신 마지막 HumanMessage 사용 (Important):**

`graph.py:129` (GoogleAuthRequired 처리 블록):
```python
# 변경 전
original = state["messages"][0].content

# 변경 후
original = next(
    (
        m.content
        for m in reversed(state["messages"])
        if isinstance(m, HumanMessage) and isinstance(m.content, str)
    ),
    "",
)
```

**커밋:**
```bash
git add src/panager/scheduler/tool.py src/panager/agent/graph.py src/panager/bot/client.py
git commit -m "fix: scheduler bot=None 버그, messages 빈 리스트 가드, pending 메시지 인덱스 수정"
```

---

### Task 2: Google Auth 강화 — blocking HTTP, None 가드, full Credentials, _execute 안전화

**Files:**
- Modify: `src/panager/google/auth.py`
- Modify: `src/panager/google/credentials.py`
- Modify: `src/panager/google/calendar/tool.py`

**Fix 1 — blocking HTTP calls → asyncio.to_thread (Important):**

`auth.py`의 두 동기 HTTP 호출을 비동기로 감싸기:

```python
# exchange_code 안 (line 54)
await asyncio.to_thread(flow.fetch_token, code=code)

# refresh_access_token 안 (line 72)
await asyncio.to_thread(creds.refresh, Request())
```

`import asyncio` 추가 필요.

**Fix 2 — refresh_token None 가드 (Critical):**

`exchange_code` 에서 `creds.refresh_token`이 None이면 즉시 오류:
```python
if creds.refresh_token is None:
    raise ValueError(
        "Google OAuth가 refresh_token을 반환하지 않았습니다. "
        "prompt=consent로 재시도하세요."
    )
```

**Fix 3 — creds.token None 가드 (Important):**

`refresh_access_token` 에서 refresh 후 token 검증:
```python
await asyncio.to_thread(creds.refresh, Request())
if creds.token is None:
    raise RuntimeError("토큰 갱신 실패: 새 access token을 받지 못했습니다.")
return creds.token, expires_at
```

**Fix 4 — full Credentials 객체 (Important):**

`credentials.py:27` 현재 token만 담긴 Credentials → refresh 가능한 full Credentials:
```python
from panager.google.auth import get_settings as _get_google_settings

return Credentials(
    token=tokens.access_token,
    refresh_token=tokens.refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=_get_google_settings().google_client_id,
    client_secret=_get_google_settings().google_client_secret,
)
```

**Fix 5 — _execute None 반환 대응 (Important):**

`credentials.py:30` 반환 타입을 `dict | None`으로 변경:
```python
async def _execute(request) -> dict | None:
```

`calendar/tool.py:54`에서 None 가능성 대응:
```python
calendars_result = await _execute(service.calendarList().list()) or {}
calendars = calendars_result.get("items", [])

# for loop 안에서도:
result = await _execute(...) or {}
for evt in result.get("items", []):
```

**Fix 6 — datetime timezone 비교 안전화 (Critical):**

`credentials.py:22` naive datetime 처리:
```python
expires_at = tokens.expires_at
if expires_at.tzinfo is None:
    expires_at = expires_at.replace(tzinfo=timezone.utc)
if expires_at <= datetime.now(timezone.utc):
    ...
```

**커밋:**
```bash
git add src/panager/google/auth.py src/panager/google/credentials.py src/panager/google/calendar/tool.py
git commit -m "fix: Google auth blocking HTTP 비동기화, None 가드, full Credentials, datetime timezone"
```

---

### Task 3: datetime timezone 안전성, tasks KeyError, memory 안전화

**Files:**
- Modify: `src/panager/scheduler/tool.py`
- Modify: `src/panager/google/tasks/tool.py`
- Modify: `src/panager/memory/repository.py`

**Fix 1 — scheduler naive datetime → timezone 처리 (Important):**

`scheduler/tool.py:31`:
```python
import zoneinfo
trigger_dt = datetime.fromisoformat(trigger_at)
if trigger_dt.tzinfo is None:
    trigger_dt = trigger_dt.replace(tzinfo=zoneinfo.ZoneInfo("Asia/Seoul"))
```

(make_schedule_create 내부 schedule_create 함수와 레거시 schedule_create 함수 둘 다 적용. 단, Task 4에서 레거시 삭제 예정이므로 factory 버전만 수정해도 무방.)

**Fix 2 — tasks item['title'] KeyError (Important):**

`tasks/tool.py:39`:
```python
f"- [{item['id']}] {item.get('title', '(제목 없음)')}"
```

**Fix 3 — memory fetchrow None 가드 (Critical):**

`memory/repository.py:21`:
```python
row = await conn.fetchrow(...)
if row is None:
    raise RuntimeError("INSERT INTO memories RETURNING id가 행을 반환하지 않았습니다.")
return UUID(str(row["id"]))
```

**Fix 4 — memory embedding 포맷 강화 (Important):**

`memory/repository.py`에서 `str(embedding)` → 부동소수점 안전 포맷:
```python
def _format_embedding(embedding: list[float]) -> str:
    return "[" + ",".join(repr(x) for x in embedding) + "]"
```

`save_memory`와 `search_memories` 두 곳 모두 `str(embedding)` → `_format_embedding(embedding)` 으로 교체.

**커밋:**
```bash
git add src/panager/scheduler/tool.py src/panager/google/tasks/tool.py src/panager/memory/repository.py
git commit -m "fix: scheduler timezone 처리, tasks title KeyError, memory fetchrow None 가드, embedding 포맷"
```

---

### Task 4: 레거시 tool 제거 (보안)

**Files:**
- Modify: `src/panager/memory/tool.py`
- Modify: `src/panager/scheduler/tool.py`

`user_id`를 LLM에 노출하는 standalone 레거시 tool 객체와 관련 Input 클래스 삭제.

**`memory/tool.py`에서 삭제:**
- `_MemorySaveInputLegacy` 클래스
- `_MemorySearchInputLegacy` 클래스
- `@tool` 데코레이터가 붙은 모듈 레벨 `memory_save` 함수
- `@tool` 데코레이터가 붙은 모듈 레벨 `memory_search` 함수
- `# Standalone tool objects kept for backward compatibility` 주석 섹션 전체

**`scheduler/tool.py`에서 삭제:**
- `_ScheduleCreateInputLegacy` 클래스
- `_ScheduleCancelInputLegacy` 클래스
- `@tool` 데코레이터가 붙은 모듈 레벨 `schedule_create` 함수
- `@tool` 데코레이터가 붙은 모듈 레벨 `schedule_cancel` 함수
- `# Standalone tool objects kept for backward compatibility` 주석 섹션 전체

**커밋:**
```bash
git add src/panager/memory/tool.py src/panager/scheduler/tool.py
git commit -m "fix: user_id를 LLM에 노출하는 레거시 tool 객체 제거 (보안)"
```

---

### Task 5: 타입 어노테이션 전면 보강

**Files:**
- Modify: `src/panager/logging.py`
- Modify: `src/panager/bot/handlers.py`
- Modify: `src/panager/bot/client.py`
- Modify: `src/panager/agent/graph.py`
- Modify: `src/panager/agent/state.py`
- Modify: `src/panager/api/main.py`
- Modify: `src/panager/api/auth.py`
- Modify: `src/panager/memory/tool.py`
- Modify: `src/panager/scheduler/runner.py`
- Modify: `src/panager/scheduler/tool.py`
- Modify: `src/panager/google/auth.py`
- Modify: `src/panager/google/credentials.py`
- Modify: `src/panager/google/calendar/tool.py`
- Modify: `src/panager/google/tasks/tool.py`

**변경 목록:**

| 파일 | 위치 | 변경 내용 |
|------|------|-----------|
| `logging.py:7` | `configure_logging(settings)` | `settings: Settings` 추가, `from panager.config import Settings` |
| `bot/handlers.py:16` | `_stream_agent_response` | `graph: Any, channel: discord.abc.Messageable` |
| `bot/handlers.py:53` | `handle_dm` | `bot: Any, graph: Any` (circular import 방지) |
| `bot/client.py:31` | `self.graph` | `self.graph: Any = None` 클래스 변수로 명시 |
| `bot/client.py:33` | `self.auth_complete_queue` | `asyncio.Queue[dict[str, int \| str \| None]]` |
| `agent/graph.py:36` | `_build_tools` return | `-> list` 유지하되 docstring에 `list[BaseTool]` 명시 |
| `agent/graph.py:68` | `_agent_node` return | `-> dict[str, list]` |
| `agent/graph.py:107` | `_make_tool_node(bot)` | `bot: Any` |
| `agent/graph.py:143` | `build_graph` | `checkpointer: Any, bot: Any = None -> Any` |
| `agent/state.py:11` | `messages` | `Annotated[list[BaseMessage], add_messages]` + `from langchain_core.messages import BaseMessage` |
| `api/main.py:8` | `create_app(bot)` | `bot: Any` |
| `api/auth.py:13` | `google_login` | `-> RedirectResponse` |
| `api/auth.py:19` | `google_callback` | `-> HTMLResponse` |
| `memory/tool.py:33,44` | factory functions | `-> Any` (StructuredTool은 langchain 내부 타입) |
| `scheduler/runner.py:21,50` | `bot` params | `bot: Any` |
| `scheduler/tool.py:27,59` | factory functions | `-> Any` |
| `google/auth.py:51` | `exchange_code` return | `-> dict[str, str \| datetime]` |
| `google/credentials.py:30` | `_execute` params | `request: Any` |
| `google/calendar/tool.py:13` | `_build_service` | `-> Any` |
| `google/tasks/tool.py:11` | `_build_service` | `-> Any` |

**커밋:**
```bash
git add src/panager/
git commit -m "feat: 전체 타입 어노테이션 보강 (logging, handlers, graph, state, api, scheduler, google)"
```

---

### Task 6: LSP 노이즈 정리

**Files:**
- Modify: `src/panager/agent/graph.py`
- Modify: `src/panager/google/auth.py`
- Modify: `src/panager/bot/client.py`
- Modify: `tests/test_config.py`
- Modify: `tests/agent/test_graph.py`

**Fix 1 — Settings() call-arg suppression:**

`graph.py:23`, `auth.py:20`, `client.py:22`, `test_config.py:17,38`, `test_graph.py:204`에 `# type: ignore[call-arg]` 추가.

**Fix 2 — SecretStr:**

`graph.py`:
```python
from pydantic import SecretStr
api_key=SecretStr(settings.llm_api_key),
```

**Fix 3 — _should_continue return type:**

`graph.py`:
```python
def _should_continue(state: AgentState) -> str:
```

**Fix 4 — psycopg DictRow:**

`client.py`:
```python
from psycopg.rows import dict_row

self._pg_conn = await psycopg.AsyncConnection.connect(
    settings.postgres_dsn_asyncpg, autocommit=True, row_factory=dict_row
)
```

**Fix 5 — AgentState TypedDict cast in tests:**

`tests/agent/test_graph.py` 3곳의 `state = {...}`:
```python
from panager.agent.state import AgentState
state: AgentState = {
    "user_id": ...,
    ...
}
```

**커밋:**
```bash
git add src/panager/ tests/
git commit -m "fix: LSP 타입 오류 정리 (Settings call-arg, SecretStr, _should_continue, DictRow, AgentState)"
```

---

### Task 7: 전체 테스트 및 push

```bash
uv run pytest tests/agent/ tests/bot/ tests/google/ tests/memory/test_tool.py tests/scheduler/test_tool.py tests/test_config.py tests/test_logging.py -v
git push origin dev
```
