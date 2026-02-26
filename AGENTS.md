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
src/panager/
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
└── db/                 # Database Connection & Alembic Migrations
```

---

## ⚙️ Environment Setup
1. **Copy Template**: `cp .env.example .env`
2. **LLM Configuration**: Set `LLM_API_KEY` (OpenAI compatible).
3. **Database**: `POSTGRES_PASSWORD` must be set for local/docker use.
4. **Discord**: Create a bot on [Discord Developer Portal](https://discord.com/developers/applications) and set `DISCORD_TOKEN`.
5. **OAuth**: Configure Google, GitHub, and Notion Client IDs/Secrets for tool integration.
