# System Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the Panager codebase into a modular, service-oriented architecture adhering to SOLID principles, improving performance with non-blocking embeddings, and decoupling the agent from Discord.

**Architecture:** Extraction of business logic into dedicated services (`MemoryService`, `GoogleService`, `SchedulerService`), introduction of Protocols (`UserSessionProvider`) for dependency inversion, and centralized application orchestration in `main.py`.

**Tech Stack:** Python 3.13, LangGraph, asyncpg, APScheduler, SentenceTransformers, Discord.py.

---

### Task 1: Scaffolding and Core Migration

**Files:**
- Create: `src/panager/core/__init__.py`, `src/panager/services/__init__.py`, `src/panager/integrations/__init__.py`, `src/panager/discord/__init__.py`
- Move: `src/panager/config.py` -> `src/panager/core/config.py`
- Move: `src/panager/logging.py` -> `src/panager/core/logging.py`
- Modify: `src/panager/db/connection.py` (update imports)

**Step 1: Create new directories**
Run: `mkdir -p src/panager/{core,services,integrations,discord}` and add `__init__.py` files.

**Step 2: Move core files and update imports**
Update `src/panager/core/config.py` and `src/panager/core/logging.py` to ensure internal imports are relative or correct.

**Step 3: Update all existing files to use `panager.core.config` and `panager.core.logging`**
Use `replaceAll` to update imports across the codebase.

**Step 4: Commit**
```bash
git add src/panager/core src/panager/services src/panager/integrations src/panager/discord
git commit -m "refactor: scaffold new directory structure and migrate core config"
```

---

### Task 2: Implement UserSessionProvider Protocol

**Files:**
- Create: `src/panager/agent/interfaces.py`

**Step 1: Define the Protocol**
```python
from __future__ import annotations
from typing import Protocol, Dict

class UserSessionProvider(Protocol):
    @property
    def pending_messages(self) -> Dict[int, str]: ...
    async def get_user_timezone(self, user_id: int) -> str: ...
```

**Step 2: Commit**
```bash
git add src/panager/agent/interfaces.py
git commit -m "feat: add UserSessionProvider protocol"
```

---

### Task 3: Memory Service Extraction

**Files:**
- Create: `src/panager/services/memory.py`
- Modify: `src/panager/memory/repository.py` (extract logic)

**Step 1: Implement MemoryService**
Move `MemoryRepository` logic and embedding generation to `MemoryService`.
Ensure `SentenceTransformer.encode` runs in `asyncio.to_thread`.

**Step 2: Write unit test for MemoryService**
Test embedding generation and search in isolation.

**Step 3: Commit**
```bash
git add src/panager/services/memory.py
git commit -m "feat: extract MemoryService with non-blocking embeddings"
```

---

### Task 4: Google Service Extraction

**Files:**
- Create: `src/panager/services/google.py`
- Create: `src/panager/integrations/google_client.py`

**Step 1: Implement GoogleService**
Centralize OAuth flow and credential management. 
Implement `GoogleService.get_calendar_service(user_id)` and `get_tasks_service(user_id)`.

**Step 2: Commit**
```bash
git add src/panager/services/google.py src/panager/integrations/google_client.py
git commit -m "feat: centralize Google API logic into GoogleService"
```

---

### Task 5: Refactor Agent Workflow (formerly graph.py)

**Files:**
- Rename: `src/panager/agent/graph.py` -> `src/panager/agent/workflow.py`
- Modify: `src/panager/agent/workflow.py`

**Step 1: Update build_graph signature**
```python
def build_graph(
    checkpointer, 
    session_provider: UserSessionProvider,
    memory_service: MemoryService,
    google_service: GoogleService,
    scheduler_service: SchedulerService
) -> CompiledGraph: ...
```

**Step 2: Update tool creation to use services**
Pass services to tool factories instead of `user_id` or `bot` directly where possible, or use the `session_provider`.

**Step 3: Commit**
```bash
git add src/panager/agent/workflow.py
git commit -m "refactor: decouple agent from discord using services and protocols"
```

---

### Task 6: Refactor Discord Bot and Handlers

**Files:**
- Move: `src/panager/bot/client.py` -> `src/panager/discord/bot.py`
- Move: `src/panager/bot/handlers.py` -> `src/panager/discord/handlers.py`

**Step 1: Update PanagerBot to implement UserSessionProvider**
Add `pending_messages` dict and `get_user_timezone` method.

**Step 2: Update handlers to use new service-based graph**
Inject services into the bot and pass them to `build_graph`.

**Step 3: Commit**
```bash
git add src/panager/discord/
git commit -m "refactor: update discord bot and handlers to use new architecture"
```

---

### Task 7: Main Entry Point

**Files:**
- Create: `src/panager/main.py`

**Step 1: Implement application bootstrap**
Initialize DB pool, services, API (as background task), and then the bot.

**Step 2: Commit**
```bash
git add src/panager/main.py
git commit -m "feat: add main entry point for application orchestration"
```

---

### Task 8: Final Cleanup and Verification

**Step 1: Remove legacy directories**
`rm -rf src/panager/memory src/panager/google src/panager/scheduler src/panager/bot`

**Step 2: Run full test suite**
Run: `make test`

**Step 3: Commit**
```bash
git commit -m "chore: remove legacy code and finalize refactoring"
```
