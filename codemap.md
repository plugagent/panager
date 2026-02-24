# Repository Atlas: Panager

## Responsibility
Panager is an agentic personal manager bot that resides in Discord DMs. It assists users by managing their Google Calendar and Tasks, storing long-term memories using semantic search, and scheduling personal notifications. It leverages LangGraph for complex reasoning and PostgreSQL for both persistent memory and conversation state.

## System Entry Points & Root Assets
- `src/panager/main.py`: The main application entry point that initializes all services and starts the bot and API server.
- `AGENTS.md`: The definitive guide for developers and agents. Contains architectural notes, coding standards, and operational commands.
- `pyproject.toml`: Dependency and environment manifest. Uses `uv` for lightning-fast package management and `hatchling` as the build backend.
- `Makefile`: Task runner for the development lifecycle. Standardizes commands for local DB setup, migrations, testing, and deployment.
- `Dockerfile`: Production deployment blueprint. Implements a multi-stage build to minimize image size and pre-caches the `sentence-transformers` model for faster cold starts.
- `alembic.ini`: Configuration for database schema migrations.

## Directory Map (Aggregated)
| Directory | Responsibility Summary | Detailed Map |
|-----------|------------------------|--------------|
| `src/panager/` | **Composition Root** orchestrating the application lifecycle and sub-module coordination. | [View Map](src/panager/codemap.md) |
| `src/panager/agent/` | Reasoning engine using LangGraph with **Closure-based Tool Factories** and context-aware message trimming. | [View Map](src/panager/agent/codemap.md) |
| `src/panager/api/` | Web server (FastAPI) dedicated to handling Google OAuth callbacks and web-based flows. | [View Map](src/panager/api/codemap.md) |
| `src/panager/core/` | Cross-cutting concerns: Pydantic-based configuration, structured logging, and custom exceptions. | [View Map](src/panager/core/codemap.md) |
| `src/panager/db/` | Database infrastructure managing connection pools for PostgreSQL/pgvector. | [View Map](src/panager/db/codemap.md) |
| `src/panager/discord/` | User interface layer implementing a **Streaming UI Pattern** and debounced real-time message edits. | [View Map](src/panager/discord/codemap.md) |
| `src/panager/integrations/` | Low-level wrappers for external services (Google APIs) with robust error handling. | [View Map](src/panager/integrations/codemap.md) |
| `src/panager/services/` | Business logic layer implementing **Strategy** (NotificationProvider), **Persistence**, and **Lazy Loading** patterns. | [View Map](src/panager/services/codemap.md) |

## Design Patterns
- **Agentic Workflow (ReAct)**: Uses LangGraph's `StateGraph` for structured, stateful multi-turn reasoning and tool orchestration.
- **Composition Root**: Centralized initialization in `main.py` that wires services, agent, and bot interfaces.
- **Closure-based Tool Factory**: Dynamically binds user session context (`user_id`) to tool execution scope.
- **Strategy Pattern**: `NotificationProvider` decouples the scheduling engine from the Discord delivery mechanism.
- **Persistence Pattern**: Ensures scheduled task durability via PostgreSQL before in-memory queuing.
- **Lazy Loading**: Defers heavy resource initialization (e.g., SentenceTransformer models) until first use to optimize startup.
- **Service Layer**: Business logic is encapsulated in `services/`, abstracting `integrations/` and `db/`.
- **Concurrency Control**: User-level locks (`asyncio.Lock`) in the Discord handler prevent state race conditions.

## Data & Control Flow
1. **Trigger**: System starts via `main.py`. External triggers come from Discord (`discord/handlers.py`) or the internal Scheduler (`services/scheduler.py`).
2. **Context Resolution**: `agent/workflow.py` loads conversation history from PostgreSQL and retrieves relevant long-term memories via `services/memory.py` (semantic search).
3. **Reasoning & Tool Execution**: The LLM determines the next action. Tools (Calendar, Tasks, Scheduler) are invoked via their respective `services`, which interact with `integrations` or `db`.
4. **Feedback & Streaming**: Agent responses are streamed back to Discord with debouncing.
5. **Persistence**: The conversation state is checkpointed in PostgreSQL using `AsyncPostgresSaver`.

## Integration Points
- **Discord API**: Primary user interface for DM interactions (via `discord.py`).
- **Google Workspace API**: Calendar and Tasks management (OAuth2 / REST API).
- **PostgreSQL / pgvector**: Persistent storage for LangGraph checkpoints and semantic memory (vector embeddings).
- **OpenAI / LLM Providers**: Core reasoning engine via LangChain/LangGraph.
