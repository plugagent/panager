# src/panager/

This is the root package of the Panager application, containing the entry point and the core architectural structure.

## Responsibility

The `src/panager/` directory serves as the **Composition Root** of the application. Its primary responsibilities include:
- **Orchestration:** Coordinating the lifecycle of the system (startup, service initialization, and graceful shutdown).
- **Dependency Injection:** Wiring together domain services, the agent workflow, and communication interfaces.
- **Resource Management:** Initializing and cleaning up database connection pools and LangGraph checkpoint savers.
- **Entrypoint:** Hosting `main.py`, which serves as the application's main entry point.

## Design

- **Service-Oriented Composition:** Uses a hub-and-spoke model where `main.py` (the hub) initializes various domain services and injects them into the agent and bot (the spokes).
- **Asynchronous Orchestration:** Leverages `asyncio` to run the Discord bot and a FastAPI server (`uvicorn`) concurrently.
- **Persistent State:** Utilizes PostgreSQL for both application data (via `asyncpg`) and agent checkpoints (via LangGraph's `AsyncPostgresSaver`).
- **Standard Layout:** Follows the `src` layout for better package isolation and maintainability.

## Flow

1. **Bootstrap:** `main.py` loads `Settings` and configures the global logging system.
2. **Infrastructure Initialization:**
   - Initializes the `asyncpg` pool for service-level DB access.
   - Sets up `psycopg` connection for the LangGraph `AsyncPostgresSaver` and runs checkpoint cleanup based on TTL.
3. **Service Layer Setup:** Instantiates `MemoryService`, `GoogleService`, and `SchedulerService`.
4. **Agent Compilation:** Calls `build_graph` to construct the LangGraph state machine, injecting the initialized services and the bot.
5. **Interface Activation:**
   - Launches a FastAPI instance (`api/`) in a background task to handle OAuth callbacks.
   - Restores existing schedules from the database.
   - Starts the `PanagerBot` (`discord/`) to begin listening for user interactions.
6. **Graceful Shutdown:** Intercepts termination signals to close DB pools and cancel background tasks cleanly.

## Package Structure & Integration

- **`main.py`**: The application entry point and composition root.
- **`agent/`**: Defines the LangGraph workflow, state schemas, and agent-specific tools.
- **`services/`**: Encapsulates business logic for long-term memory, Google Workspace integration, and task scheduling.
- **`discord/`**: Implements the Discord bot interface, message handling, and response streaming.
- **`api/`**: Provides a FastAPI application for web-based flows (e.g., Google OAuth).
- **`db/`**: Manages database connection lifecycle and schema migrations.
- **`core/`**: Contains cross-cutting concerns like configuration, logging, and custom exceptions.
- **`integrations/`**: Low-level client implementations for external APIs.
- **`scheduler/`**: Placeholder for background task execution logic (currently managed via `services/scheduler.py`).

