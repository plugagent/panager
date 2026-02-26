# AGENTS.md (Index & Developer Guide)

This guide provides the necessary context and standards for agentic coding agents operating in the **panager** repository.

---

## 🚀 Project Index & Overview
- **Core:** Discord DM bot (personal manager) using **LangGraph Multi-Agent** logic.
- **Goal:** Support 100+ tools with complex cross-domain (composite) task execution.
- **Stack:** Python 3.13+, `uv`, PostgreSQL (`pgvector`), Google/GitHub/Notion APIs.
- **Entrypoint:** `uv run python -m panager.main`

---

## 📁 Repository Structure
```text
├── alembic/            # Database Migrations (Alembic)
└── src/panager/
    ├── main.py             # Composition Root & App Entrypoint
    ├── agent/              # Modular & Semantic Discovery Logic
    │   ├── workflow.py     # Main StateGraph (Discovery -> Planner -> Executor)
    │   ├── supervisor.py   # Dynamic Planner (LLM-based task orchestration)
    │   ├── registry.py     # ToolRegistry & Semantic Search (pgvector)
    │   └── state.py        # AgentState (TypedDict with add_messages)
    ├── tools/              # Domain-specific Tools (e.g., google.py, github.py)
    ├── services/           # Business Logic Layer (API Wrappers & Token Mgmt)
    ├── integrations/       # Low-level API Clients
    ├── core/               # Shared Config, Logging, Exceptions
    ├── discord/            # UI Layer (Handlers, Streaming, Auth UX)
    ├── api/                # FastAPI (OAuth callbacks & GitHub webhooks)
    └── db/                 # Database Connection Logic
```

---

## ⚙️ Environment Setup
0. **Install uv**: Ensure `uv` is installed as the primary package manager.
1. **Copy Template**: `cp .env.example .env`
2. **LLM Configuration**: Set `LLM_API_KEY` (OpenAI compatible).
3. **Database**: `POSTGRES_PASSWORD` must be set for local/docker use.
4. **Discord**: Create a bot on [Discord Developer Portal](https://discord.com/developers/applications) and set `DISCORD_TOKEN`.
5. **OAuth**: Configure Google, GitHub, and Notion Client IDs/Secrets for tool integration.

---

## 🛠 Commands & Testing

### 🏗 Essential Makefile Commands
- `make dev`: Run the bot locally with hot-reload (uses native `uv`).
- `make test`: Run all tests using the test database.
- `make db`: Start the PostgreSQL test database in Docker.
- `make migrate-test`: Run database migrations on the test DB.

### 🧪 Running Tests (Pytest)
To run a specific test file or a single test case:
```bash
# Run a specific test file
uv run pytest tests/test_main_logic.py

# Run a single test function
uv run pytest tests/test_main_logic.py::test_some_function
```

### 💬 Discord Direct Testing
When testing via Discord DM:
1. Ensure the bot is running (`make dev`).
2. Send a message to the bot in Discord.
3. Check logs for real-time execution details:
   - If running via `make dev`, logs appear in the terminal.
   - If running via Docker, use `make dev-logs`.

---

## 📜 Coding Standards & Tool Development

### 🐍 Python & Style
- **Imports**: Always include `from __future__ import annotations` at the top of every Python file for postponed evaluation of annotations.
- **Formatting**: Use `ruff` for linting and formatting. Adhere to the project's `.ruff.toml` if present.
- **Naming**:
  - `snake_case` for variables, functions, and modules.
  - `PascalCase` for classes.
  - Constants should be `UPPER_SNAKE_CASE`.
- **Types**: Mandatory type annotations for all function signatures and complex variables. Use `| None` for optional types (e.g., `str | None`) rather than `Optional[str]`.

### 🛠 Tool Development (CRITICAL)
- **Location**: Place all new tools in `src/panager/tools/` using domain-specific filenames (e.g., `google.py`, `github.py`).
- **Decorator**: Every tool must be decorated with `@tool` from `langchain_core.tools`.
- **Return Type**: **MANDATORY**: Every tool MUST return a **JSON-formatted string**. Do not return raw objects, dictionaries, or plain text unless it's strictly required by the caller. This ensures compatibility with the agent's observation handling.
- **Documentation**: Provide clear, descriptive docstrings for every tool, explaining parameters and return values.

### 🛡 Error Handling & Logging
- **Exceptions**: Use specialized exception classes defined in `src/panager/core/exceptions.py`.
- **Logging**: Use the project-wide logger. Avoid `print()` statements; use `logger.info()`, `logger.error()`, etc., to provide visibility into agent execution.

