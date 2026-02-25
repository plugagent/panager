# Repository Atlas: Panager

## Responsibility
Panager is an agentic personal manager bot that resides in Discord DMs. It assists users with a wide range of tasks including managing Google Calendar/Tasks, GitHub repository activities, Notion database entries, and long-term memory via semantic search. It leverages a hierarchical Multi-Agent architecture using LangGraph, with a central Supervisor orchestrating specialized Workers.

## System Entry Points & Root Assets
- `src/panager/main.py`: The main application entry point that initializes all services and starts the bot and API server.
- `AGENTS.md`: The definitive guide for developers and agents. Contains architectural notes, coding standards, and operational commands.
- `pyproject.toml`: Dependency and environment manifest. Uses `uv` for lightning-fast package management.
- `Makefile`: Task runner for the development lifecycle. Standardizes commands for local DB setup, migrations, testing, and deployment.
- `Dockerfile`: Production deployment blueprint with multi-stage build and pre-cached ML models.

## Directory Map (Aggregated)
| Directory | Responsibility Summary | Detailed Map |
|-----------|------------------------|--------------|
| `src/panager/` | **Composition Root** orchestrating the application lifecycle and multi-agent topology. | [View Map](src/panager/codemap.md) |
| `src/panager/agent/` | **Hierarchical Multi-Agent Orchestrator** using a Supervisor pattern to delegate to specialized workers. | [View Map](src/panager/agent/codemap.md) |
| `src/panager/agent/github/` | **GitHub Worker Agent** for repository management and webhook-driven proactive tasks. | [View Map](src/panager/agent/github/codemap.md) |
| `src/panager/agent/google/` | **Google Worker Agent** integrating Calendar and Tasks with OAuth lifecycle management. | [View Map](src/panager/agent/google/codemap.md) |
| `src/panager/agent/memory/` | **Memory Worker Agent** for user-specific semantic storage and retrieval. | [View Map](src/panager/agent/memory/codemap.md) |
| `src/panager/agent/notion/` | **Notion Worker Agent** for structured data logging and page management. | [View Map](src/panager/agent/notion/codemap.md) |
| `src/panager/agent/scheduler/` | **Scheduler Worker Agent** for proactive notifications and background task execution. | [View Map](src/panager/agent/scheduler/codemap.md) |
| `src/panager/api/` | FastAPI server handling **OAuth callbacks** and **GitHub webhooks** for proactive events. | [View Map](src/panager/api/codemap.md) |
| `src/panager/core/` | Infrastructure layer: Configuration, structured logging, and global exceptions. | [View Map](src/panager/core/codemap.md) |
| `src/panager/db/` | Database layer managing PostgreSQL connection pools and migrations (Alembic). | [View Map](src/panager/db/codemap.md) |
| `src/panager/discord/` | UI layer implementing **Streaming UI** and handling auth-interrupt user flows. | [View Map](src/panager/discord/codemap.md) |
| `src/panager/services/` | Logic layer providing unified interfaces for external APIs (GitHub, Google, Notion). | [View Map](src/panager/services/codemap.md) |

## Design Patterns
- **Supervisor-Worker (Multi-Agent)**: A central Supervisor (`supervisor.py`) routes user requests to specialized sub-graphs (Workers).
- **Hierarchical Planning**: The system breaks down complex multi-provider requests into sub-tasks delegated to domain-specific agents.
- **Interrupt/Resume Workflow**: LangGraph's checkpointer handles state persistence and UI interrupts (e.g., OAuth requirements).
- **Proactive Triggering**: GitHub webhooks and internal schedulers trigger the agent with system-initiated context.
- **Closure-based Tool Factory**: Dynamically binds session context (user/auth) to tool execution scope.
- **Service-Repository Pattern**: Decouples business logic from external API clients and database operations.

## Data & Control Flow
1. **Trigger**: Input via Discord (Human), GitHub Webhooks (System), or internal Scheduler (System).
2. **Orchestration**: `supervisor.py` analyzes the request and routes it to one or more workers (Google, GitHub, Notion, etc.).
3. **Worker Execution**: Each worker uses domain-specific tools and logic. If auth is missing, an interrupt is triggered for the user.
4. **Proactive Reflection**: After events (like a GitHub push), the system may proactively prompt the user to record memories or logs.
5. **Streaming Output**: Debounced message edits stream the supervisor's reasoning and worker results back to Discord.

## Integration Points
- **Discord API**: Main UI for interaction and real-time streaming feedback.
- **GitHub API**: Webhook ingestion and repository management (OAuth2).
- **Google Workspace**: Calendar and Tasks integration with automated OAuth flow.
- **Notion API**: Structured document and database management.
- **PostgreSQL / pgvector**: Persistent state and semantic memory storage.
- **LangGraph / OpenAI**: Agent orchestration and high-level reasoning.
