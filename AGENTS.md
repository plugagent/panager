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

