# src/panager/

This is the root package of the Panager application, containing the entry point and the core architectural structure.

## Responsibility

The `src/panager/` directory coordinates the various components of the Panager system. Its primary job is to:
- Orchestrate the lifecycle of the application (startup, service initialization, shutdown).
- Provide a clear structure for sub-modules responsible for different domains (agent, api, discord, services, etc.).
- Contain the `main.py` entry point which binds all layers together.

## Design

- **Orchestration Layer:** `main.py` serves as the glue, initializing infrastructure (DB, Logging), services (Memory, Google, Scheduler), and interfaces (Discord Bot, FastAPI).
- **Service-Oriented Architecture:** Business logic is encapsulated in the `services/` directory and injected into the agent workflow and the bot.
- **Asynchronous Execution:** Built entirely on `asyncio` to handle concurrent Discord interactions, background scheduling, and API requests.
- **Persistence:** Uses PostgreSQL for both application state (memories) and agentic state (LangGraph checkpoints).

## Flow

1. **Bootstrap:** `main.py` loads `Settings` and configures logging.
2. **Infrastructure:** Database pools and the LangGraph `AsyncPostgresSaver` are initialized.
3. **Services:** Domain-specific services (`MemoryService`, `GoogleService`, `SchedulerService`) are instantiated.
4. **Agent Workflow:** The LangGraph state machine is constructed in `agent/workflow.py`, with services injected as dependencies.
5. **Interface Activation:**
   - The FastAPI server (`api/`) is launched in the background to handle OAuth flows.
   - The Discord bot (`discord/`) is started to interact with users.
6. **Interaction:** User DMs are handled by the bot, which delegates reasoning to the LangGraph agent, which in turn calls tools powered by the services.

## Integration

- **Entry Point:** `main.py` - The application entry point.
- **Agent:** `agent/` - LangGraph-based reasoning and tool definitions.
- **Interface:** `discord/` and `api/` - User-facing communication channels.
- **Business Logic:** `services/` - Core functionality (Google, Memory, Scheduling).
- **Infrastructure:** `db/` and `core/` - Persistence, configuration, and logging.
- **External:** `integrations/` - Low-level clients for external APIs (Google).
