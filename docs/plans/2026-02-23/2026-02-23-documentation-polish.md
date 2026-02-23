# Documentation Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update AGENTS.md, clean up the directory structure, and enhance the root Atlas with a system flow diagram.

**Architecture:** Consistency between codebase reality and architectural documentation.

**Tech Stack:** Markdown, Git, Cartography skill.

---

### Task 1: Update AGENTS.md to Reflect Refactored Structure

**Files:**
- Modify: `AGENTS.md`

**Step 1: Update AGENTS.md**

Update Project Overview, Commands (tests), and Project Structure to match the new `src/panager/` layout.

```markdown
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

# Tests that don't require DB (no env vars needed):
uv run pytest tests/panager/agent/ tests/panager/discord/ tests/panager/services/ tests/test_config.py tests/test_logging.py -v
```

---

## Project Structure

```
src/panager/
├── main.py            # Entry point: Initializes all services, bot, and API
├── agent/             # LangGraph workflow, state, and tool definitions
├── services/          # Core logic: Memory (pgvector), Google, Scheduler
├── integrations/      # Low-level clients for external APIs (Google)
├── discord/           # UI Layer: Discord Client and DM handlers
├── api/               # Web Layer: FastAPI app for OAuth callbacks
├── core/              # Shared: Config, Logging, Exceptions
└── db/                # Infrastructure: PostgreSQL connection pool
```
```

[Note: Adjust other sections to use `panager.core.config` etc. if necessary]

**Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: 리팩토링된 구조에 맞춰 AGENTS.md 최신화"
```

### Task 2: Remove Empty Scheduler Directory

**Step 1: Delete directory**

Run: `rm -rf src/panager/scheduler/`

**Step 2: Commit**

```bash
git add .
git commit -m "refactor: 사용되지 않는 빈 scheduler 디렉토리 삭제"
```

### Task 3: Enhance Root codemap.md with Data Flow

**Files:**
- Modify: `codemap.md`

**Step 1: Add Data Flow Section**

```markdown
## System Data Flow

1. **User Interaction**: User sends a DM to the Discord Bot (`discord/handlers.py`).
2. **Context Resolution**: The handler retrieves the user's LangGraph thread and state from PostgreSQL.
3. **Agent Reasoning**: The LangGraph state machine (`agent/workflow.py`) processes the message:
   - **Memory Check**: Searches long-term memory (`services/memory.py`) for relevant past context.
   - **LLM Call**: Decides whether to reply directly or use tools.
4. **Tool Execution**: If needed, the agent calls tools (Calendar, Tasks, Scheduler) via `services/` and `integrations/`.
5. **Streaming Output**: The agent's response is streamed back to Discord in real-time with debouncing.
6. **State Persistence**: The conversation state and any new memories are saved back to PostgreSQL.
```

**Step 2: Commit**

```bash
git add codemap.md
git commit -m "docs: 루트 코드맵에 시스템 데이터 흐름 섹션 추가"
```

### Task 4: Final State Update and Cleanup

**Step 1: Update Cartography state**

Run: `python3 ~/.config/opencode/skills/cartography/scripts/cartographer.py update --root ./`

**Step 2: Verify and Commit**

```bash
git add .slim/cartography.json
git commit -m "docs: 문서 최신화 완료 및 상태 업데이트"
```
