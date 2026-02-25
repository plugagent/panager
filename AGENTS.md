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

## Agent Workflow

에이전트가 이 코드베이스에서 작업할 때는 코드 품질과 안정성을 보장하기 위해 아래의 표준 작업 절차를 엄격히 준수해야 합니다.

### 1. 디자인 우선 원칙 (Design-First Principle)
- **계획 선행**: 기능 추가, 리팩토링, 구조 변경 등 코드 수정 전에는 반드시 `docs/plans/` 디렉토리에 마크다운 형식의 설계/구현 계획 문서(예: `docs/plans/feature-name.md`)를 작성합니다.
- **승인 후 실행**: 계획을 작성한 후에는 반드시 사용자(User) 또는 아키텍처 담당 에이전트의 리뷰와 승인을 거쳐야만 실제 코딩 작업으로 진입할 수 있습니다.

### 2. 표준 작업 사이클 (Standard Work Cycle)
복잡한 문제를 해결하기 위해 에이전트는 다음 5단계를 거쳐 작업합니다:
1. **Understand (이해)**: 요구사항과 시스템의 현재 상태, 연관된 기존 컨텍스트를 분석합니다.
2. **DELEGATE (위임)**: 작업 성격에 따라 최적화된 에이전트 롤을 활용하고 역할을 나눕니다.
   - `@oracle`: 아키텍처 설계, 전략 수립, 코드 리뷰 및 고난도 디버깅 조언 (Read-Only)
   - `@explorer`: 코드베이스 구조 파악 및 관련 심볼 탐색 전문
   - `@fixer`: 실제 코드 구현, 버그 수정, 테스트 작성 및 리팩토링 실행
3. **Plan (계획)**: `docs/plans/`에 구체적이고 실행 가능한 단계별 계획을 문서화합니다.
4. **Execute (실행)**: 수립된 계획에 따라 전용 브랜치에서 코드를 수정합니다.
5. **Verify (검증)**: `make test` 및 `uv run ruff check`를 통해 사이드 이펙트가 없음을 증명합니다.

### 3. 클린 깃 정책 (Clean Git Policy)
- **직접 수정 금지**: `dev` 또는 `main` 브랜치에서 직접 코드를 수정하거나 커밋하는 것을 엄격히 금지합니다.
- **브랜치/워크트리 분리**: 모든 작업(단순 문서 수정 포함)은 작업 목적을 나타내는 명확한 이름의 전용 기능 브랜치에서 수행해야 합니다.
- **안전한 병합 (Finishing a branch)**: 작업 종료 시 반드시 `finishing-a-development-branch` 스킬(또는 동등한 절차)을 준수합니다.
  - 최신 기준 브랜치(Base branch)로부터 Rebase하여 충돌을 해결합니다.
  - 병합 전 전체 테스트 스위트가 통과하는지 확인합니다.
  - 커밋 메시지 컨벤션에 맞춰 불필요한 커밋을 정리한 뒤 병합/PR을 진행합니다.

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

배포는 GitHub Actions 기반의 CD 프로세스를 통해 자동화되어 있습니다.
- **GHCR**: `main` 브랜치 푸시 시 Docker 이미지가 빌드되어 GitHub Container Registry(`ghcr.io`)에 게시됩니다.
- **Cloudflare SSH**: Cloudflare Tunnel/SSH를 통해 운영 서버에 보안 접속하여 `docker compose pull` 및 컨테이너 재시작을 수행합니다.

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

### JSON-First Tool Response

모든 도구(tool)의 응답은 구조화된 **JSON 문자열**이어야 합니다. 이는 LLM이 도구의 실행 결과(성공 여부, 데이터 등)를 명확하게 인지하도록 돕습니다.

```python
# Good
return json.dumps({"status": "success", "event_id": "...", "summary": "회의 예약 완료"})

# Bad
return "회의가 예약되었습니다."
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
- **Supervisor Pattern:** 메인 그래프는 `supervisor_node`를 통해 요청을 분석하고 전문가 워커(`GoogleWorker`, `MemoryWorker`, `SchedulerWorker`)에게 작업을 위임합니다.
- **Message trimming:** `trim_messages(..., token_counter="approximate")`가 `supervisor_node` 및 워커 노드에서 실행되어 토큰 사용량을 제한합니다.
- **Google auth (Interrupt):** Google 인증 필요 시 `interrupt()`를 사용하여 그래프 실행을 중단하고, 사용자가 인증을 완료하면 `Command(resume="auth_success")`를 통해 중단된 지점부터 자동 재개합니다.
- **Streaming:** `graph.astream(..., stream_mode="messages")`와 `STREAM_DEBOUNCE`를 사용하여 디스코드 메시지를 실시간으로 업데이트합니다.
- **에이전트 재진입 (`trigger_task`):** 스케줄러에 의해 예약된 작업이 실행될 때 `trigger_task`를 통해 에이전트가 특정 컨텍스트와 함께 자동 재진입할 수 있습니다.
- **`AgentState` 플래그:** 현재 실행이 시스템 트리거(예: 알림)에 의한 것인지 구분하기 위해 `is_system_trigger` 플래그를 `AgentState`에서 관리합니다.
- **Migrations:** Alembic manages DB schema; always run `make migrate-test` before tests that touch the DB.
