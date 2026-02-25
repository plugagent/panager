# src/panager/

This is the root package of the Panager application, containing the entry point and the core architectural structure.

## Responsibility

The `src/panager/` directory serves as the **Composition Root** of the application. Its primary responsibilities include:
- **Orchestration:** Coordinating the lifecycle of the system (startup, service initialization, and graceful shutdown).
- **Dependency Injection:** Wiring together domain services, the multi-agent supervisor workflow, and communication interfaces.
- **Resource Management:** Initializing and cleaning up database connection pools and LangGraph checkpoint savers.
- **Entrypoint:** Hosting `main.py`, which serves as the application's main entry point.

## Design

- **Supervisor-Worker Architecture:** Employs a hierarchical multi-agent design where a central Supervisor orchestrates specialized worker agents (Google, GitHub, Notion, Memory, Scheduler).
- **Service-Oriented Composition:** Uses a hub-and-spoke model where `main.py` initializes various domain services and injects them into the agent and bot.
- **Asynchronous Orchestration:** Leverages `asyncio` to run the Discord bot and a FastAPI server (`uvicorn`) concurrently.
- **Persistent State:** Utilizes PostgreSQL for application data (via `asyncpg`), agent checkpoints (via LangGraph's `AsyncPostgresSaver`), and external integration tokens.

## Flow

1. **Bootstrap:** `main.py` loads `Settings` and configures global logging.
2. **Infrastructure Initialization:** Sets up `asyncpg` for services and `psycopg` for LangGraph `AsyncPostgresSaver`.
3. **Service Layer Setup:** Instantiates `MemoryService`, `GoogleService`, `GithubService`, `NotionService`, and `SchedulerService`.
4. **Agent Compilation:** Calls `build_graph` to construct the multi-agent `StateGraph`, injecting services and configuring the Supervisor-Worker topology.
5. **Interface Activation:**
   - Launches FastAPI (`api/`) for OAuth callbacks and GitHub webhooks.
   - Restores existing schedules.
   - Starts `PanagerBot` (`discord/`) for DM interaction.
6. **Graceful Shutdown:** Ensures clean closure of DB pools and background tasks.

## Integration Points

- **`main.py`**: Composition root initializing all sub-packages.
- **`agent/`**: Implements the LangGraph multi-agent workflow and supervisor logic.
- **`services/`**: Encapsulates business logic for integrations (Google, GitHub, Notion) and core utilities (Memory, Scheduler).
- **`discord/`**: Main user interface via Discord Gateway.
- **`api/`**: Public web interface for OAuth and webhooks.
- **`db/`**: Database lifecycle management and migrations.
- **`core/`**: Shared configuration, logging, and exceptions.

