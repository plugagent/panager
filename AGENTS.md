# AGENTS.md (Index & Developer Guide)

## CRITICAL GUIDELINES

1. **Single Message Policy**: All responses must be provided by **editing** the initial "Thinking..." message. Never create duplicate messages. (Refer to [UX Standards Section 1](#1-single-message-policy))
2. **Real-time Visibility**: While the user is waiting, the agent's internal state must be updated and shown in real-time (e.g., `Analyzing intent...` > `Searching for tools...` > `Executing tool: ~...`). (Refer to [UX Standards Section 2](#2-step-by-step-visibility))
3. **Streaming**: The AI's final response must be streamed character by character. (Refer to [UX Standards Section 3](#3-streaming-and-finalization))
4. **No Emoji**: Do not use emojis in status messages or any response text. (Refer to [UX Standards Section 3](#3-streaming-and-finalization))
5. **JSON Return**: All tools MUST return a **JSON-formatted string**. (Refer to [Tool Development Section](#tool-development-critical))
6. **Absolute Paths**: Always use absolute paths, including the project root, when reading or writing files. (Refer to [Python & Style Section](#python--style))
7. **Conventional Commits**: Commit messages must be written in Korean and strictly follow the specification. (Refer to [Workflow & Commits Section](#workflow--commits))

---

This guide provides the necessary context and standards for agentic coding agents operating in the **panager** repository.

---

## Project Index & Overview
- **Core:** Discord DM bot (personal manager) using **LangGraph Multi-Agent** logic.
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
To run a specific test file or a single test case:
```bash
# Run a specific test file
uv run pytest tests/test_main_logic.py

# Run a single test function
uv run pytest tests/test_main_logic.py::test_some_function
```

### Discord Direct Testing
When testing via Discord DM:
1. Ensure the bot is running (`make dev`).
2. Send a message to the bot in Discord.
3. Check logs for real-time execution details:
   - If running via `make dev`, logs appear in the terminal.
   - If running via Docker, use `make dev-logs`.

---

## Coding Standards & Tool Development

### Python & Style
- **Imports**: Always include `from __future__ import annotations` at the top of every Python file for postponed evaluation of annotations.
- **Formatting**: Use `ruff` for linting and formatting. Adhere to the project's `.ruff.toml` if present.
- **Naming**:
  - `snake_case` for variables, functions, and modules.
  - `PascalCase` for classes.
  - Constants should be `UPPER_SNAKE_CASE`.
- **Types**: Mandatory type annotations for all function signatures and complex variables. Use `| None` for optional types (e.g., `str | None`) rather than `Optional[str]`.
- **Paths**: **CRITICAL**: Always use absolute paths for file I/O. Use the project root directory as a base. (Refer to Critical Guideline 6)

### <a name="tool-development-critical"></a>Tool Development (CRITICAL)
- **Location**: Place all new tools in `src/panager/tools/` using domain-specific filenames (e.g., `google.py`, `github.py`).
- **Decorator**: Every tool must be decorated with `@tool` from `langchain_core.tools`.
- **Return Type**: **MANDATORY**: Every tool MUST return a **JSON-formatted string**. Do not return raw objects, dictionaries, or plain text unless it's strictly required by the caller. This ensures compatibility with the agent's observation handling. (Refer to Critical Guideline 5)
- **Documentation**: Provide clear, descriptive docstrings for every tool, explaining parameters and return values.

### Error Handling & Logging
- **Exceptions**: Use specialized exception classes defined in `src/panager/core/exceptions.py`.
- **Logging**: Use the project-wide logger. Avoid `print()` statements; use `logger.info()`, `logger.error()`, etc., to provide visibility into agent execution.

---

## <a name="workflow--commits"></a>Workflow & Commits

### Git Workflow
- **Branching**: All development should occur on feature branches branching off the `dev` branch.
- **Commits**: Strictly follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. (Refer to Critical Guideline 7)
  - **Subject**: **MANDATORY** Korean (e.g., `feat: 구글 캘린더 도구 추가`).
  - **Body**: **MANDATORY** Korean description of the changes (e.g., `구글 캘린더 도구를 추가하고 OAuth2 인증 흐름을 구현함.`).
  - **Format**:
    ```text
    <type>(<scope>): <subject>

    <body>
    ```

### Conventional Commit Types
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (formatting, white-space, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

---

## Agent State Management

### LangGraph AgentState
- **Definition**: The global state is managed via the `AgentState` TypedDict in `src/panager/agent/state.py`.
- **Message Handling**: Use `Annotated[list[AnyMessage], add_messages]` for the `messages` key. This ensures that new messages from nodes are appended to the existing history.
- **Cross-Node Communication**:
  - Nodes should only modify the fields they are responsible for.
  - Use `NotRequired` for optional fields to keep the state clean.
  - Key fields include `user_id`, `username`, `messages`, and `memory_context`.

### Persistence & thread_id
- **Thread IDs**: Every conversation with a user must be associated with a unique `thread_id` (Discord Channel ID).
- **Checkpointers**: We use `PostgresSaver` to persist the state of each thread. This allows the agent to remember context across restarts.
- **Resuming**: When a user sends a new message, the `thread_id` is used to load the previous state, ensuring the LLM has access to history.

### Node Best Practices
1. **Idempotency**: Ensure that nodes can be re-run safely if an error occurs.
2. **State Cleanup**: Always clear transient flags (e.g., `is_system_trigger`) once consumed.
3. **Observation Handling**: Tools MUST return JSON strings, which are then added to the state as `ToolMessage` objects. (Refer to Critical Guideline 5)

---

## UX and Discord Interaction Standards

### <a name="1-single-message-policy"></a>1. Single Message Policy
- **Principle**: The bot leaves exactly **one message** in response to a single user input. (Refer to Critical Guideline 1)
- **Method**: Send an initial "Thinking..." message, and reflect all subsequent state changes and AI responses by **editing** that message.

### <a name="2-step-by-step-visibility"></a>2. Step-by-Step Visibility
- Share the agent's working steps with the user in real-time to increase transparency. (Refer to Critical Guideline 2)
- **Status Message Guide**:
  - `discovery`: "Analyzing intent..."
  - `supervisor`: "Searching for relevant tools and planning..."
  - `tool_executor`: "Executing tool: `{tool_name}`..."
  - `auth_interrupt`: "Security authentication is required."

### <a name="3-streaming-and-finalization"></a>3. Streaming and Finalization
- LLM's text response (`AIMessageChunk`) is streamed immediately upon receipt to provide a live feel. (Refer to Critical Guideline 3)
- Tool execution results or authentication links naturally combine at the end of the response.
- Remove UI elements (cursor, etc.) indicating the "Thinking" state once the final response is complete.
- **No Emoji**: Do not use emojis in status messages or any response text. (Refer to Critical Guideline 4)

---

## Advanced Patterns

### Auth Interrupt
- **HITL (Human-In-The-Loop)**: If an authentication exception such as `GoogleAuthRequired` occurs during tool execution, call LangGraph's `interrupt` function to pause the graph.
- **Flow**: The agent should not catch the exception directly but throw it up; the `auth_interrupt` node detects this, sends the authentication URL to the user, and waits for approval.

### Tool Metadata and Search
- **Domain Metadata**: Every tool must specify a domain, e.g., `@tool(..., metadata={"domain": "google"})`.
- **Role**: This metadata is used as a key identifier for semantic search filtering in the `discovery_node` and authentication URL routing in the `tool_executor`.

### Scheduler Convention
- **Trigger Prefix**: Messages triggered by the scheduler have a `[SCHEDULED_EVENT]` prefix.
- **Discovery**: The `discovery_node` removes this prefix before performing a tool search, ensuring that tool search works correctly even for automated tasks.

### Async SDK Handling (asyncio.to_thread)
- **Blocking SDK**: When calling synchronous external SDKs like Google or GitHub, you must use `asyncio.to_thread()` to prevent blocking the event loop.

---

## CI/CD & Deployment

### GitHub Actions Pipeline
- **Dev Pipeline (`dev.yml`)**: Pushing to the `dev` branch automatically triggers the `Lint (Ruff) -> Test (Pytest) -> Build -> Deploy` process.
- **Test DB**: In the CI environment, a dedicated PostgreSQL service container with `pgvector` is used for actual DB integration testing.

### Deployment Method
- **Tailscale**: Connect to the deployment server via Tailscale for private network security.
- **Registry**: Built images are stored in `ghcr.io` (GitHub Container Registry)에 저장되며, 서버에서 `docker compose pull`을 통해 업데이트됩니다.
- **Model Init**: Language model initialization and weight management are handled by a separate image via `Dockerfile.model`.

### Pull Request Rules
- **Template**: When creating a PR, you must follow the format in `.github/PULL_REQUEST_TEMPLATE.md` and record changes, test results, screenshots, etc., in detail.
