# src/panager/db/

Database connection management and schema lifecycle.

## Responsibility

- **Connection Lifecycle**: Managing asynchronous PostgreSQL connection pool using `asyncpg`.
- **Global Access**: Providing a shared connection pool (`get_pool`).

## Design

- **Async Connection Pool**: Uses `asyncpg.Pool`.
- **Initialization Pattern**: Explicit `init_pool` ensures DB is ready.
- **Singleton Access**: Internal `_pool` variable accessible via `get_pool()`.

## Flow

1. **Startup**: `bot/client.py` calls `init_pool(dsn)`.
2. **Operation**: Modules needing DB access call `get_pool()`.
3. **Shutdown**: `bot/client.py` calls `close_pool()`.

## Integration

- **Entrypoint**: Initialized by `PanagerBot`.
- **Consumers**: `memory/`, `scheduler/`.
- **Migrations**: Managed by Alembic in root `alembic/`.
