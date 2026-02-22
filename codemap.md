# Repository Atlas: Panager

## Project Responsibility
Panager is an agentic personal manager bot that resides in Discord DMs. It assists users by managing their Google Calendar and Tasks, storing long-term memories using semantic search, and scheduling personal notifications. It leverages LangGraph for complex reasoning and PostgreSQL for both persistent memory and conversation state.

## System Entry Points
- `src/panager/main.py`: The main application entry point that initializes all services and starts the bot and API server.
- `pyproject.toml`: Project metadata, dependencies, and configuration.
- `alembic.ini`: Database migration configuration.
- `Makefile`: Development and deployment commands.

## Directory Map (Aggregated)

| Directory | Responsibility Summary | Detailed Map |
|-----------|------------------------|--------------|
| `src/panager/` | Root package orchestrating the application lifecycle and sub-module coordination. | [View Map](src/panager/codemap.md) |
| `src/panager/agent/` | Reasoning engine using LangGraph to manage state, conversation history, and tool execution. | [View Map](src/panager/agent/codemap.md) |
| `src/panager/api/` | Web server (FastAPI) primarily dedicated to handling Google OAuth callbacks. | [View Map](src/panager/api/codemap.md) |
| `src/panager/core/` | Cross-cutting concerns: Type-safe configuration, structured logging, and custom exceptions. | [View Map](src/panager/core/codemap.md) |
| `src/panager/db/` | Database infrastructure, managing asynchronous connection pools for PostgreSQL. | [View Map](src/panager/db/codemap.md) |
| `src/panager/discord/` | User interface layer; handles Discord DMs and streams agent responses in real-time. | [View Map](src/panager/discord/codemap.md) |
| `src/panager/integrations/` | Low-level wrappers for external services (Google APIs) with robust error handling. | [View Map](src/panager/integrations/codemap.md) |
| `src/panager/services/` | Business logic services for semantic memory (pgvector), Google APIs, and task scheduling. | [View Map](src/panager/services/codemap.md) |
