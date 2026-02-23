# src/panager/services/

## Responsibility
Core service layer responsible for managing external integrations (Google APIs), persistent memory with semantic search (pgvector), and scheduled task execution (APScheduler). It acts as a bridge between the agentic logic and persistent state/external resources.

## Design
The services follow a singleton-like pattern (usually instantiated once at startup) and utilize:
- **Service Pattern**: Centralized classes (`GoogleService`, `MemoryService`, `SchedulerService`) managing specific domains.
- **Protocol/Interface**: `NotificationProvider` protocol in `scheduler.py` for decoupling notification delivery from scheduling logic.
- **Lazy Loading**: `MemoryService` lazy-loads the heavy `SentenceTransformer` model to optimize startup time.
- **Async Execution**: Heavy CPU or blocking I/O tasks (model loading, API building, embedding generation) are delegated to threads via `asyncio.to_thread`.

## Flow
1. **Google Auth**: `GoogleService` generates auth URLs -> exchanges codes for tokens -> stores in DB -> provides valid `Credentials` for API calls.
2. **Memory/Search**: Content/Query -> `MemoryService` generates vector embedding -> DB vector similarity search (`<=>`) or insert.
3. **Scheduling**: `SchedulerService.add_schedule` -> DB persistence -> `APScheduler` job queue -> Triggered callback -> Agent reentry (`trigger_task`) or `NotificationProvider` execution -> DB status update.

## Integration
- **Database**: All services integrate with PostgreSQL via `asyncpg` for persistence (tokens, memories, schedules).
- **External APIs**: `google-api-python-client` for Calendar and Tasks.
- **Machine Learning**: `sentence-transformers` for generating text embeddings.
- **Notification**: `SchedulerService` depends on an external `NotificationProvider` (usually the Discord bot client).
- **Consumers**: These services are primarily consumed by LangChain/LangGraph tools and handlers in `src/panager/agent/` and `src/panager/discord/`.
