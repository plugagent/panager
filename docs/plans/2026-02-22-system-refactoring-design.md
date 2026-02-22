# Design Doc: System Refactoring for SOLID and Modularity

- **Date:** 2026-02-22
- **Topic:** Refactoring the Panager codebase to adhere to SOLID principles, improve performance, and enhance maintainability through better directory structure and decoupling.

## 1. Objectives
- **Single Responsibility Principle (SRP):** Break down "God Objects" (like `PanagerBot`) into focused services.
- **Dependency Inversion Principle (DIP):** Decouple the agent from the Discord bot implementation using Protocols.
- **Improved Performance:** Prevent event loop blocking by moving CPU-intensive tasks to separate threads.
- **Intuitive Structure:** Rename folders and files to better reflect their roles.
- **Strict Type Safety:** Remove `Any` types, add missing return types, and enforce project conventions.

## 2. Proposed Architecture

### 2.1. New Directory Structure
```text
src/panager/
├── core/                  # Configuration, logging, and constants
├── db/                    # Database pool and maintenance
├── services/              # Business logic (Memory, Scheduler, Google)
├── integrations/          # External service clients (Google API)
├── agent/                 # LangGraph workflow and state
├── discord/               # Discord-specific implementation
├── api/                   # FastAPI endpoints (OAuth callbacks)
└── main.py                # Entry point for the entire application
```

### 2.2. Core Components

#### **Services (SRP)**
- `MemoryService`: Handles embedding generation (via `asyncio.to_thread`) and vector search.
- `GoogleService`: Centralizes OAuth token management and Google API client creation.
- `SchedulerService`: Manages `APScheduler` jobs and database persistence for schedules.
- `AuthSessionManager`: Manages the state of pending user requests during OAuth flows.

#### **Interfaces (DIP)**
- `UserSessionProvider` (Protocol): Defined in `agent/interfaces.py`. Used by the agent to interact with the host environment (Discord) without direct coupling.

#### **Application Orchestration**
- `main.py`: Responsible for initializing the database pool, starting the API server, initializing services, and launching the Discord bot. This removes the "God Object" burden from `PanagerBot`.

## 3. Implementation Details

### 3.1. Performance & Stability
- Move `SentenceTransformer.encode` to `MemoryService` using `asyncio.to_thread`.
- Fix LangGraph state overwrite issues in `handlers.py` by ensuring proper reducer usage or state management.
- Implement pagination (`nextPageToken`) for all Google API list operations.
- Handle Discord's 2000-character message limit in `_stream_agent_response`.

### 3.2. Code Style & Conventions
- Add `from __future__ import annotations` to all files.
- Replace `Any` with specific types.
- Standardize import ordering (stdlib -> third-party -> local).
- Remove all "Legacy" code and deprecated tools.

## 4. Migration Plan
1. **Scaffold Structure:** Create new directories and `main.py`.
2. **Core & DB:** Move config, logging, and database logic.
3. **Services Layer:** Extract Memory, Scheduler, and Google logic into services.
4. **Agent Refactoring:** Implement Protocols and update the LangGraph workflow.
5. **Discord Integration:** Refactor the bot to use the new services and interfaces.
6. **Final Cleanup:** Remove old directories and verify via tests.

## 5. Success Criteria
- All tests pass (including new unit tests for services).
- No event loop blocking during embedding generation.
- Clear separation between agent logic and Discord implementation.
- 100% type annotation coverage in refactored modules.
