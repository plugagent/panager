# AGENTS.md

Guide for agentic coding agents working in this repository.

---

## Project Overview

**panager** — Discord DM bot (personal manager) backed by LangGraph, PostgreSQL (pgvector), and Google APIs.

- **Language:** Python 3.13+
- **Package manager:** `uv` (always use `uv run ...`, never `python ...` directly)
- **Layout:** src layout — package root is `src/panager/`
- **Entrypoint:** `python -m panager.main`

---

## Commands

### Development

```bash
make dev          # start test DB + hot-reload bot
make db           # start test PostgreSQL (localhost:5433) only
make db-down      # stop test DB
make migrate-test # apply alembic migrations to test DB
```

### Testing

```bash
# Full test suite (starts DB automatically)
make test

# If test DB is already running:
POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run pytest -v

# Single test file:
POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run pytest tests/panager/agent/test_workflow.py -v

# Single test function:
POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run pytest tests/panager/agent/test_workflow.py::test_graph_builds_successfully -v

# Tests that don't require DB (no env vars needed):
uv run pytest tests/panager/agent/ tests/panager/discord/ tests/panager/google/ tests/panager/services/ tests/test_config.py tests/test_logging.py -v
```

**Note:** `tests/test_db_connection.py` and `tests/memory/test_repository.py` require a live PostgreSQL connection (use `make test` or `make db` first).

### Linting

Ruff is used (no formal config — ad-hoc). Run manually if needed:

```bash
uv run ruff check src/
uv run ruff format src/
```

### Production

```bash
make up    # docker compose up -d --build
make down  # docker compose down
```

---

## Project Structure

```
src/panager/
├── main.py            # Entrypoint
├── core/              # Config, Logging, Exceptions
│   ├── config.py
│   ├── logging.py
│   └── exceptions.py
├── discord/           # Discord bot & handlers
│   ├── bot.py
│   └── handlers.py
├── agent/             # LangGraph workflow & tools
│   ├── workflow.py    # StateGraph definition
│   ├── tools.py       # Agent tools
│   └── state.py       # AgentState TypedDict
├── services/          # Business logic (Google, Memory, Scheduler)
├── integrations/      # External API clients (Google, etc.)
├── api/               # FastAPI app (OAuth callback)
├── db/                # Database connection & migrations
└── scheduler/         # Background tasks & runner
tests/                 # mirrors src/panager/ structure
docs/plans/            # implementation plan markdown files
```

---

## Code Style

### Imports

Always start files with `from __future__ import annotations`. Group imports: stdlib → third-party → local (`panager.*`), separated by blank lines.

```python
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import discord
from langchain_core.messages import HumanMessage

from panager.core.config import Settings
from panager.db.connection import get_pool
```

### Type Annotations

Use on all function signatures (arguments + return type). Prefer `X | None` over `Optional[X]`. Use `TypedDict`, `Annotated`, `NotRequired` as needed.

```python
async def _cleanup_old_checkpoints(conn: psycopg.AsyncConnection, ttl_days: int) -> None:
    ...

_pool: asyncpg.Pool | None = None
```

### Naming

| Kind | Convention | Example |
|------|-----------|---------|
| Functions / variables | `snake_case` | `build_graph`, `user_id` |
| Private / internal | `_leading_underscore` | `_get_settings()`, `_pool` |
| Classes | `PascalCase` | `PanagerBot`, `Settings` |
| Constants | `UPPER_SNAKE_CASE` | `STREAM_DEBOUNCE`, `SCOPES` |
| Module logger | always `log` | `log = logging.getLogger(__name__)` |

### Logging

Use stdlib `logging` to get a module-level logger. Use `%s` format strings (not f-strings) in log calls. Pass `exc_info=True` on warnings that capture exceptions.

```python
log = logging.getLogger(__name__)

log.info("봇 시작 완료: %s", str(self.user))
log.warning("정리 실패 (봇은 계속 시작)", exc_info=True)
log.info("알림 발송 완료", extra={"user_id": user_id})
```

### Error Handling

- Non-fatal startup operations: wrap in `try/except Exception` + `log.warning(..., exc_info=True)`, let bot continue.
- Domain-specific errors: use custom exception classes (e.g. `GoogleAuthRequired`), catch specifically before bare `Exception`.
- Silent swallowing only for explicitly expected failures (e.g. removing a job that no longer exists).

```python
# Non-fatal
try:
    await _cleanup_old_checkpoints(self._pg_conn, settings.checkpoint_ttl_days)
except Exception:
    log.warning("checkpoint 정리 실패 (봇은 계속 시작)", exc_info=True)

# Domain exception
except GoogleAuthRequired:
    result = f"Google 계정 연동이 필요합니다.\n{get_auth_url(user_id)}"
except Exception as exc:
    result = f"오류 발생: {exc}"
```

### Async

Use `asyncio` natively throughout. Wrap sync calls with `asyncio.to_thread()`. Use `@lru_cache` on sync factory functions only (not async).

```python
@lru_cache
def _get_settings() -> Settings:
    return Settings()

# Sync Google API in async context
result = await asyncio.to_thread(request.execute)
```

### Docstrings

Optional on trivial functions; use short Korean one-liners or brief paragraphs on non-obvious ones. No Args/Returns sections.

```python
class GoogleAuthRequired(Exception):
    """Google 계정 미연동 또는 scope 부족 시 발생하는 예외."""

async def memory_save(content: str) -> str:
    """중요한 내용을 장기 메모리에 저장합니다."""
```

---

## Testing Conventions

- `asyncio_mode = "auto"` in `pyproject.toml` — all async tests run automatically.
- Use `@pytest.mark.asyncio` on async test functions (explicit, even though auto mode is on).
- Mock LLM calls with `MagicMock` / `AsyncMock`; use `unittest.mock.patch` to patch at the import site (e.g. `panager.agent.workflow.trim_messages`).
- Tests that need DB fixtures: use `@pytest.fixture(autouse=True)` async fixtures.
- Test files mirror the `src/panager/` structure under `tests/`.

---

## Configuration (Environment Variables)

All config is via `pydantic-settings` `Settings` class (`src/panager/core/config.py`). Copy `.env.example` → `.env` for local dev.

Key env vars: `DISCORD_TOKEN`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `POSTGRES_*`, `GOOGLE_CLIENT_*`, `GOOGLE_REDIRECT_URI`, `LOG_FILE_PATH`, `CHECKPOINT_MAX_TOKENS`, `CHECKPOINT_TTL_DAYS`.

In tests, always `monkeypatch.setenv(...)` every required field explicitly — do not rely on `.env` file loading in tests.

---

## Commit Convention

Conventional Commits with **Korean** message bodies:

```
feat: 봇 시작 시 TTL 초과 checkpoint 자동 정리
fix: test_settings_loads_from_env에 LLM_MODEL 환경변수 명시 설정
docs: checkpoint trim & TTL 구현 플랜 문서 추가
refactor: handle_dm 스트리밍 방식으로 교체
```

---

## Key Architectural Notes

- **LangGraph checkpointer:** `AsyncPostgresSaver` with `thread_id = str(user_id)` — conversations persist across restarts.
- **Message trimming:** `trim_messages(..., token_counter="approximate")` applied in `_agent_node` before LLM invocation to bound token usage.
- **Google auth:** `GoogleAuthRequired` exception propagates from tool → tool node → returned as message to user with OAuth URL.
- **Streaming:** `graph.astream(..., stream_mode="messages")` with debounced Discord message edits (`STREAM_DEBOUNCE`).
- **Migrations:** Alembic manages DB schema; always run `make migrate-test` before tests that touch the DB.
