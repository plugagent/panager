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
3. **Database**: Configure `POSTGRES_PASSWORD` and `POSTGRES_PORT`.
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
# Run all tests and measure coverage
uv run pytest --cov=src/panager tests/
```

To run a specific test file or a single test case:
```bash
# Run a specific test file
uv run pytest tests/test_main_logic.py

# Run a single test function
uv run pytest tests/test_main_logic.py::test_some_function
```

### Discord Direct Testing
Follow these steps for verification in the actual environment:
1. Run the bot: `make dev`
2. Send a Discord DM: Send a direct message to the bot to verify functionality.
3. Check logs: Monitor real-time execution details.
   - Local run: Check terminal output.
   - Docker run: Use `make dev-logs`.

---

## Coding Standards & Tool Development

### Python & Style
- **Imports**: Always include `from __future__ import annotations` at the top of every Python file.
- **Formatting**: Use `ruff` for linting and formatting.
- **Strict Typing**: **MANDATORY**: Avoid `Any`.
    - Use `TypedDict` for node outputs.
    - Use Pydantic `BaseModel` for complex structures (e.g., `DiscoveredTool`, `PendingReflection`).
- **Async SDK Handling**: When calling blocking (Sync) SDKs like Google or GitHub, you MUST use `asyncio.to_thread()` to avoid blocking the event loop.
- **Paths**: Always use absolute paths relative to the project root.

### <a name="tool-development-critical"></a>Tool Development (CRITICAL)
- **Location**: Place in `src/panager/tools/` by domain.
- **Decorator**: Use the `@tool` decorator.
- **Metadata**: Every tool must specify a domain, e.g., `@tool(..., metadata={"domain": "..."})`. This is used for semantic search and auth routing.
- **Return Type**: **MANDATORY**: Every tool MUST return a **JSON-formatted string**.
- **OAuth Safety**: External OAuth `state` parameters MUST include a domain prefix (e.g., `notion_`, `github_`) to ensure string type recognition by external APIs.

---

## <a name="workflow--commits"></a>Workflow & Commits

### Git Workflow
- **Branching**: Create feature branches from the `dev` branch.
- **Commits**: Adhere to [Conventional Commits](https://www.conventionalcommits.org/).
  - **Subject**: **Korean** (e.g., `feat: 구글 캘린더 도구 추가`).
  - **Body**: **Korean** detailed description.

### Conventional Commit Types
- `feat`: A new feature (새로운 기능 추가)
- `fix`: A bug fix (버그 수정)
- `docs`: Documentation only changes (문서 수정)
- `style`: Formatting, missing semi colons, etc; no code change (코드 의미에 영향을 주지 않는 변경)
- `refactor`: Refactoring production code (성능 개선이나 버그 수정을 포함하지 않는 코드 구조 변경)
- `test`: Adding missing tests, refactoring tests (테스트 코드 추가 및 수정)
- `chore`: Updating build tasks, package manager configs, etc (빌드 업무 수정, 패키지 매니저 설정 등)

---

## Agent State Management

### LangGraph AgentState
- **Definition**: Managed in `src/panager/agent/state.py`.
- **Message Handling**: Use `Annotated[list[AnyMessage], add_messages]` to accumulate conversation history.
- **Node Best Practices**:
    1. **Idempotency**: Design nodes to be safe for re-execution after an error.
    2. **State Cleanup**: Clear one-time flags like `is_system_trigger` immediately after use.

### Persistence & Resumption
- **Thread IDs**: Linked with Discord channel IDs to maintain sessions.
- **Checkpointers**: Use `PostgresSaver` to persist state.
- **Auto-Resumption**:
    1. If an auth interrupt occurs, save `auth_message_id` and `auth_request_url` to the state.
    2. After receiving the OAuth callback, call `astream(None, ...)` to resume immediately from the point of interruption.

---

## UX and Discord Interaction Standards

### 1. Single Message Policy
- The bot leaves only **one message** per user input. It continuously **edits** the initial "Thinking..." message to show the final result.

### 2. Step-by-Step Visibility
- Update progress in real-time to increase transparency:
  - `discovery`: "의도를 파악하고 있습니다..."
  - `agent`: "관련 도구를 검색하고 계획을 세우는 중입니다..."
  - `tool_executor`: "도구 실행 중: `{tool_name}`..."
  - `auth_interrupt`: "보안 인증이 필요합니다."

### 3. Streaming and Finalization
- The AI's final response is streamed character by character.
- **State Clearing**: Upon successful completion, nodes MUST clear `auth_request_url` and `auth_message_id` to prevent legacy UI elements from appearing.

---

## Advanced Patterns

### Auth Interrupt & Resume
- **Mechanism**: Use LangGraph's `interrupt()` when authentication is required.
- **Single Message UX**: Use the saved `auth_message_id` to naturally transition the auth link message into the result message.

### GitHub Push Reflection
- **Webhook**: Receive push event -> Convert to `PendingReflection` (Pydantic) model -> Trigger agent task.
- **Prompting**: Keep trigger commands simple; let the agent read structured data from the state.

---

## CI/CD & Deployment

### Infrastructure Configuration
- **Port Synchronization**: To prevent conflicts in deployment environments, synchronize the host port, container internal port (`PGPORT`), and app connection port using a single `POSTGRES_PORT` variable in `.env`.

### GitHub Actions Pipeline
- **Dev Pipeline**: Pushing to the `dev` branch automatically triggers `Lint -> Test -> Build -> Deploy`.
- **Test DB**: The CI environment uses a dedicated PostgreSQL container with `pgvector` for actual database integration testing.

### Deployment Method
- **Security**: Securely connect to the deployment server via Tailscale.
- **Registry**: Built images are stored in `ghcr.io`, and the server updates via `docker compose pull`.
