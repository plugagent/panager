# AGENTS.md

Guide for agentic coding agents working in the **panager** repository.

## Project Overview
- **Core:** Discord DM bot (personal manager) using **Multi-Agent LangGraph**.
- **Stack:** Python 3.13+, `uv` (package manager), PostgreSQL (pgvector), Google/GitHub/Notion APIs.
- **Entrypoint:** `python -m panager.main` (Use `uv run` to execute).

## Commands
### Development & DB
```bash
make dev           # Start test DB + hot-reload bot
make db            # Start test PostgreSQL (localhost:5433)
make migrate-test  # Apply alembic migrations to test DB
```
### Testing & Linting
```bash
make test          # Full suite (auto-starts DB)
# Single test file
POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run pytest tests/agent/test_workflow.py -v
# Single test function
POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run pytest tests/agent/test_workflow.py::test_graph_builds_successfully -v
# Linting
uv run ruff check src/ && uv run ruff format src/
```

## Project Structure
```
src/panager/
├── main.py            # Entrypoint & Composition Root
├── core/              # Config, Logging, Exceptions
├── discord/           # Discord bot & streaming handlers
├── agent/             # Multi-Agent Logic
│   ├── supervisor.py  # Orchestrator (Router)
│   ├── workflow.py    # Multi-agent graph definition
│   ├── state.py       # AgentState (TypedDict)
│   └── [worker]/      # Specialized sub-agents (google, github, notion, etc.)
├── services/          # Business logic layer (External API wrappers)
├── integrations/      # Low-level API clients
├── api/               # FastAPI (OAuth callbacks & webhooks)
└── db/                # PostgreSQL connection & migrations
```

## Code Style
### Imports & Formatting
Always start with `from __future__ import annotations`. Use `ruff` for formatting.
Group imports: **stdlib → third-party → local (`panager.*`)**, separated by blank lines.

### Types & Naming
- Use type annotations for all signatures. Prefer `X | None` over `Optional[X]`.
- **Snake_case** for functions/vars, **PascalCase** for classes, **UPPER_SNAKE_CASE** for constants.
- Internal members start with `_`. Module logger is always named `log`.

```python
log = logging.getLogger(__name__)

async def get_user_data(user_id: str) -> dict | None:
    _internal_cache = {}
    ...
```

### Error Handling & Logging
- Use stdlib `logging` with `%s` format strings. Use `exc_info=True` for caught exceptions.
- Domain errors use custom classes (e.g., `GoogleAuthRequired`).
- Non-fatal operations should be wrapped in `try/except` and logged as warnings.

```python
try:
    await service.call()
except GoogleAuthRequired:
    log.info("Auth required for user %s", user_id)
    raise
except Exception:
    log.warning("Operation failed but continuing", exc_info=True)
```

### Tool Responses
**MANDATORY:** All tool outputs must be **structured JSON strings** for LLM reliability.
```python
return json.dumps({"status": "success", "summary": "Event created", "event_id": "..."})
```

## Key Architectural Notes
- **Multi-Agent Design:** Hierarchical Supervisor-Worker pattern. The Supervisor routes tasks to specialized workers (Google, GitHub, etc.) via sub-graphs.
- **Persistence:** LangGraph `AsyncPostgresSaver` with `thread_id = str(user_id)`.
- **Interrupt/Resume:** Graphs use `interrupt` for external requirements (e.g., OAuth authentication).
- **Proactive Triggers:** GitHub webhooks and internal schedulers trigger the agent with `is_system_trigger=True` to initiate proactive conversations.
- **Message Trimming:** `trim_messages` is applied at the Supervisor level to bound token usage.

## Testing Conventions
- Use `@pytest.mark.asyncio` for async tests.
- Mock external APIs (Google, GitHub) using `unittest.mock.patch` or specialized fixtures.
- DB-dependent tests require `POSTGRES_HOST` and `POSTGRES_PORT` env vars.
- Test files should mirror the `src/` directory structure.

## Configuration
All configuration is managed via `pydantic-settings` in `src/panager/core/config.py`.
Environment variables are prefixed with nothing (direct mapping).
Key variables: `DISCORD_TOKEN`, `LLM_API_KEY`, `POSTGRES_URL`, `GOOGLE_CLIENT_ID`, etc.

## Commit Convention
Conventional Commits with **Korean** bodies:
- `feat: ...` (기능 추가)
- `fix: ...` (버그 수정)
- `refactor: ...` (코드 리팩토링)
- `docs: ...` (문서 수정)
