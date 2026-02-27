# AGENTS.md (Index & Developer Guide)

## CRITICAL GUIDELINES

1. **Single Message Policy**: All responses must be provided by **editing** the initial "Thinking..." message. Never create duplicate messages. (Refer to [UX Standards Section 1](#1-single-message-policy))
2. **Real-time Visibility**: While the user is waiting, the agent's internal state must be updated and shown in real-time (e.g., `Analyzing intent...` > `Executing tool: ~...`). (Refer to [UX Standards Section 2](#2-step-by-step-visibility))
3. **Streaming**: The AI's final response must be streamed character by character. (Refer to [UX Standards Section 3](#3-streaming-and-finalization))
4. **No Emoji**: Do not use emojis in status messages or any response text. (Refer to [UX Standards Section 3](#3-streaming-and-finalization))
5. **JSON Return**: All tools MUST return a **JSON-formatted string**. (Refer to [Tool Development Section](#tool-development-critical))
6. **Strict Typing**: **MANDATORY**: Never use `Any`. Define every input/output using `TypedDict` or Pydantic `BaseModel`. (Refer to [Python & Style Section](#python--style))
7. **Absolute Paths**: Always use absolute paths, including the project root, when reading or writing files. (Refer to [Python & Style Section](#python--style))
8. **Conventional Commits**: Commit messages must be written in Korean and strictly follow the specification. (Refer to [Workflow & Commits Section](#workflow--commits))

---

This guide provides the necessary context and standards for agentic coding agents operating in the **panager** repository.

---

## Project Index & Overview
- **Core:** Discord DM bot (personal manager) using **LangGraph Single-Agent** logic.
- **Goal:** Support 100+ tools with complex cross-domain (composite) task execution.
- **Stack:** Python 3.13+, `uv`, PostgreSQL (`pgvector`), Google/GitHub/Notion APIs.
- **Entrypoint:** `uv run python -m panager.main`

---

## Repository Structure
```text
├── alembic/            # Database Migrations (Alembic)
└── src/panager/
    ├── main.py             # Composition Root & App Entrypoint
    ├── agent/              # Modular & Semantic Discovery Logic
    │   ├── workflow.py     # Main StateGraph (Discovery -> Agent -> Executor)
    │   ├── agent.py        # Central Agent Logic (Tool Calling & Response)
    │   ├── registry.py     # ToolRegistry & Semantic Search (pgvector)
    │   └── state.py        # AgentState (TypedDict with Pydantic Models)
    ├── tools/              # Domain-specific Tools (e.g., google.py, github.py)
    ├── services/           # Business Logic Layer (API Wrappers & Token Mgmt)
    ├── integrations/       # Low-level API Clients
    ├── core/               # Shared Config, Logging, Exceptions
    ├── discord/            # UI Layer (Handlers, Streaming, Auth UX)
    ├── api/                # FastAPI (OAuth callbacks & GitHub webhooks)
    └── db/                 # Database Connection Logic
```

---

## Environment Setup
0. **Install uv**: Ensure `uv` is installed as the primary package manager.
1. **Copy Template**: `cp .env.example .env`
2. **LLM Configuration**: Set `LLM_API_KEY` (OpenAI compatible).
3. **Database**: `POSTGRES_PASSWORD` must be set for local/docker use.
4. **Discord**: Create a bot on [Discord Developer Portal](https://discord.com/developers/applications) and set `DISCORD_TOKEN`.
5. **OAuth**: Configure Google, GitHub, and Notion Client IDs/Secrets for tool integration.

---

## Commands & Testing

### Essential Makefile Commands
- `make dev`: Run the bot locally with hot-reload (uses native `uv`).
- `make test`: Run all tests using the test database.
- `make db`: Start the PostgreSQL test database in Docker.
- `make migrate-test`: Run database migrations on the test DB.

### Testing (Pytest)
To run all tests and check coverage (Goal: **90%+**):
```bash
# 전체 테스트 및 커버리지 측정
uv run pytest --cov=src/panager tests/
```

To run a specific test file or a single test case:
```bash
# Run a specific test file
uv run pytest tests/test_main_logic.py

# Run a single test function
uv run pytest tests/test_main_logic.py::test_some_function
```

---

## Coding Standards & Tool Development

### Python & Style
- **Imports**: Always include `from __future__ import annotations` at the top of every Python file for postponed evaluation of annotations.
- **Formatting**: Use `ruff` for linting and formatting. Adhere to the project's `.ruff.toml` if present.
- **Naming**: `snake_case` for variables/functions, `PascalCase` for classes.
- **Strict Typing**: **MANDATORY**: Avoid `Any`.
    - Use `TypedDict` for node outputs.
    - Use Pydantic `BaseModel` for complex structured data (e.g., `DiscoveredTool`, `PendingReflection`).
- **Paths**: Always use absolute paths for file I/O. Use the project root directory as a base.

### <a name="tool-development-critical"></a>Tool Development (CRITICAL)
- **Location**: Place all new tools in `src/panager/tools/`.
- **Decorator**: Every tool must be decorated with `@tool` from `langchain_core.tools`.
- **Return Type**: **MANDATORY**: Every tool MUST return a **JSON-formatted string**.
- **OAuth Safety**: External OAuth `state` parameters MUST include a domain prefix (e.g., `notion_`, `github_`) to force string type recognition by external APIs.

---

## <a name="workflow--commits"></a>Workflow & Commits

### Git Workflow
- **Branching**: All development should occur on feature branches branching off the `dev` branch.
- **Commits**: Strictly follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.
  - **Subject**: **MANDATORY** Korean (e.g., `feat: 구글 캘린더 도구 추가`).
  - **Body**: **MANDATORY** Korean description of the changes.

---

## Agent State Management

### LangGraph AgentState
- **Definition**: Managed via `AgentState` in `src/panager/agent/state.py`.
- **Message Handling**: Use `Annotated[list[AnyMessage], add_messages]` for `messages`.
- **Data Models**: Use Pydantic models for structured lists to ensure type safety during LLM interactions.

### Persistence & Resumption
- **Thread IDs**: Associated with unique Discord Channel IDs.
- **Checkpointers**: Uses `PostgresSaver` for persistence.
- **Auto-Resumption**:
    1. Auth interrupt occurs -> `auth_message_id` and `auth_request_url` are saved to state.
    2. OAuth callback received -> `PanagerBot` calls `astream(None, config=config)`.
    3. Graph resumes exactly from the interrupted point.

---

## UX and Discord Interaction Standards

### <a name="1-single-message-policy"></a>1. Single Message Policy
- **Principle**: The bot leaves exactly **one message** in response to a single user input.
- **Method**: Send an initial "Thinking..." message, and reflect all subsequent state changes by **editing** that message.

### <a name="2-step-by-step-visibility"></a>2. Step-by-Step Visibility
- **Status Message Guide**:
  - `discovery`: "의도를 파악하고 있습니다..."
  - `agent`: "관련 도구를 검색하고 계획을 세우는 중입니다..."
  - `tool_executor`: "도구 실행 중: `{tool_name}`..."
  - `auth_interrupt`: "보안 인증이 필요합니다."

### <a name="3-streaming-and-finalization"></a>3. Streaming and Finalization
- LLM's text response is streamed character by character.
- **State Clearing**: Upon successful completion, nodes MUST clear `auth_request_url` and `auth_message_id` to prevent legacy UI elements from appearing.

---

## Advanced Patterns

### Auth Interrupt & Resume
- **Mechanism**: Use LangGraph's `interrupt()` to pause execution for OAuth.
- **Resume Mode**: Pass `None` as the input state to `astream` to resume from the last checkpoint.
- **Single Message UX**: Use the saved `auth_message_id` to fetch and edit the existing authentication link message into the final result.

### GitHub Push Reflection
- **Webhook**: Receive push event -> Convert payload to `PendingReflection` (Pydantic) -> Trigger agent task.
- **Prompting**: Keep the trigger command simple; let the agent read the structured data from the `AgentState`.
