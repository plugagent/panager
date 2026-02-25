# src/panager/services/

Business logic layer orchestrating external integrations and internal data services.

## Responsibility
- **Integration Management**: Lifecycle of Google (Calendar/Tasks), GitHub (Repos/Webhooks), and Notion (DB/Pages) clients.
- **Semantic Memory**: High-dimensional vector search and storage for user context.
- **Scheduling**: Persistent task management and agent re-entry triggering.

## Design Patterns
- **Service Layer Pattern**: Centralized, stateful services managing connections and auth state.
- **Protocol-Driven Notification**: `NotificationProvider` decouples delivery from scheduling.
- **Persistence Pattern**: All integration tokens and schedules are persisted in PostgreSQL for durability.
- **Lazy Initialization**: Resource-intensive components (e.g., ML embedding models) are loaded on-demand.

## Data & Control Flow
1. **Google/GitHub/Notion**: `get_client` -> Check DB for tokens -> Refresh if needed (Google) -> Return authenticated client.
2. **Memory**: `save` (text -> embedding -> pgvector) and `search` (query -> embedding -> cosine similarity search).
3. **Scheduler**: `add_schedule` -> DB write -> APScheduler registration -> Trigger -> `NotificationProvider` or `trigger_task`.

## Integration Points
- **Database**: PostgreSQL (pgvector) for embeddings, tokens, and schedules.
- **Agent Workers**: Provides the underlying logic for specialized sub-agent tools.
- **Discord Bot**: Consumes notifications and provides the `NotificationProvider` implementation.
- **FastAPI**: Used by OAuth flows to persist credentials via service methods.
