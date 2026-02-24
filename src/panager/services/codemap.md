# src/panager/services/

## Responsibility
Core service layer acting as the orchestration bridge between the agentic logic (`panager.agent`) and external/persistent resources.
- **GoogleService**: Manages OAuth2 lifecycle and provides authenticated clients for Google Calendar/Tasks.
- **MemoryService**: Handles long-term semantic memory using vector embeddings and similarity search.
- **SchedulerService**: Manages persistent scheduled tasks, supporting both simple notifications and complex agentic re-entry commands.

## Design
- **Service Pattern**: Centralized, stateful services (`GoogleService`, `MemoryService`, `SchedulerService`) instantiated as singletons at the application level.
- **Strategy Pattern**: `NotificationProvider` protocol in `scheduler.py` decouples the scheduling engine from the delivery mechanism (Discord).
- **Persistence Pattern**: `SchedulerService` ensures durability by persisting jobs in PostgreSQL before queuing them in the `AsyncIOScheduler` memory.
- **Retry Pattern**: `SchedulerService._execute_schedule` implements exponential backoff (up to 3 retries) for resilient task execution.
- **Lazy Loading**: `MemoryService` utilizes a lazy-initialization pattern with `asyncio.Lock` for the heavy `SentenceTransformer` model to optimize bot startup time.
- **Async Thread Offloading**: Blocking I/O (Google API builds) and CPU-intensive tasks (ML embedding generation) are delegated to worker threads via `asyncio.to_thread`.

## Flow
### Scheduled Task Execution (scheduler.py)
1. **Creation**: `add_schedule` -> Write to `schedules` DB table -> Register job in `APScheduler` with `schedule_id`.
2. **Execution**: `APScheduler` trigger -> `_execute_schedule` -> Invoke `NotificationProvider.send_notification` or `trigger_task`.
3. **Agent Re-entry**: If type is `command`, `trigger_task` injects a system message into the LangGraph workflow.
4. **Completion**: DB update (`sent = TRUE`) -> Log outcome.
5. **Recovery**: `restore_schedules` (at startup) -> Query unsent future jobs from DB -> Re-populate `APScheduler` queue.

### Semantic Memory (memory.py)
1. **Save**: Content -> `_get_embedding` (CPU thread) -> INSERT into `memories` with `vector` type.
2. **Search**: Query -> `_get_embedding` -> SELECT with cosine distance operator (`<=>`) ordered by similarity.

### Google Integration (google.py)
1. **Auth**: `get_auth_url` -> User callback -> `exchange_code` -> Store encrypted/persistent tokens.
2. **Access**: `get_calendar_service`/`get_tasks_service` -> `_get_valid_credentials` -> Refresh token if expired -> Return discovery resource.

## Integration
- **Database**: PostgreSQL (via `asyncpg`) using `pgvector` for embeddings and standard tables for tokens/schedules.
- **Task Queue**: `APScheduler` (`AsyncIOScheduler`) for in-memory event timing.
- **External APIs**: Google Discovery API for Calendar/Tasks.
- **ML Engine**: `sentence-transformers` (`paraphrase-multilingual-mpnet-base-v2`) for cross-lingual embeddings.
- **Consumer**: 
    - `panager.agent.tools`: Primary consumer for business logic.
    - `panager.discord.bot`: Implements `NotificationProvider` and consumes auth flows.
    - `panager.main`: Handles service initialization and recovery.
