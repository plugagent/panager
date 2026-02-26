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

---

## 🔄 Workflow & Commits

### 🌳 Git Workflow
- **Branching**: All development should occur on feature branches branching off the `dev` branch.
- **Commits**: Strictly follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.
  - **Subject**: **MANDATORY** Korean (e.g., `feat: 구글 캘린더 도구 추가`).
  - **Body**: **MANDATORY** Korean description of the changes (e.g., `구글 캘린더 도구를 추가하고 OAuth2 인증 흐름을 구현함.`).
  - **Format**:
    ```text
    <type>(<scope>): <subject>

    <body>
    ```

### 📦 Conventional Commit Types
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (formatting, white-space, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

---

## 🧠 Agent State Management

### 🌊 LangGraph AgentState
- **Definition**: The global state is managed via the `AgentState` TypedDict in `src/panager/agent/state.py`.
- **Message Handling**: Use `Annotated[list[AnyMessage], add_messages]` for the `messages` key. This ensures that new messages from nodes are appended to the existing history.
- **Cross-Node Communication**:
  - Nodes should only modify the fields they are responsible for.
  - Use `NotRequired` for optional fields to keep the state clean.
  - Key fields include `user_id`, `username`, `messages`, and `memory_context`.

### 🧵 Persistence & thread_id
- **Thread IDs**: Every conversation with a user must be associated with a unique `thread_id` (Discord Channel ID).
- **Checkpointers**: We use `PostgresSaver` to persist the state of each thread. This allows the agent to remember context across restarts.
- **Resuming**: When a user sends a new message, the `thread_id` is used to load the previous state, ensuring the LLM has access to history.

### 🚦 Node Best Practices
1. **Idempotency**: Ensure that nodes can be re-run safely if an error occurs.
2. **State Cleanup**: Always clear transient flags (e.g., `is_system_trigger`) once consumed.
3. **Observation Handling**: Tools MUST return JSON strings, which are then added to the state as `ToolMessage` objects.

---

## 🏗 고급 개발 패턴 (Advanced Patterns)

### 🔐 인증 인터럽트 (Auth Interrupt)
- **HITL (Human-In-The-Loop)**: 도구 실행 중 `GoogleAuthRequired` 등 인증 예외가 발생하면 LangGraph의 `interrupt` 기능을 호출하여 그래프를 일시 중지합니다.
- **흐름**: 에이전트는 예외를 직접 catch하지 않고 위로 던져야 하며, `auth_interrupt` 노드가 이를 감지하여 사용자에게 인증 URL을 전송하고 승인을 기다립니다.

### 🏷 도구 메타데이터 및 검색
- **Domain Metadata**: 모든 도구는 `@tool(..., metadata={"domain": "google"})`와 같이 도메인을 명시해야 합니다.
- **역할**: 이 메타데이터는 `discovery_node`의 시맨틱 검색 필터링과 `tool_executor`의 인증 URL 라우팅 시 핵심 식별자로 사용됩니다.

### 📅 스케줄러 컨벤션
- **Trigger Prefix**: 스케줄러에 의해 트리거된 메시지는 `[SCHEDULED_EVENT]` 접두사를 가집니다.
- **Discovery**: `discovery_node`에서는 이 접두사를 제거한 후 도구 검색을 수행하므로, 자동화된 작업 시에도 도구 검색이 정상적으로 작동합니다.

### ⚡ 비동기 SDK 처리 (asyncio.to_thread)
- **Blocking SDK**: Google, GitHub 등 동기 방식으로 동작하는 외부 SDK 호출 시 반드시 `asyncio.to_thread()`를 사용하여 이벤트 루프가 차단되지 않도록 보호해야 합니다.

---

## 🚀 CI/CD 및 배포 (CI/CD & Deployment)

### 🛠 GitHub Actions 파이프라인
- **Dev Pipeline (`dev.yml`)**: `dev` 브랜치에 푸시 시 `Lint (Ruff) -> Test (Pytest) -> Build -> Deploy` 과정이 자동 실행됩니다.
- **Test DB**: CI 환경에서는 `pgvector`가 포함된 전용 PostgreSQL 서비스 컨테이너를 사용하여 실제 DB 연동 테스트를 수행합니다.

### 🌐 배포 방식
- **Tailscale**: 사설 네트워크 보안을 위해 Tailscale을 통해 배포 서버에 접속합니다.
- **Registry**: 빌드된 이미지는 `ghcr.io` (GitHub Container Registry)에 저장되며, 서버에서 `docker compose pull`을 통해 업데이트됩니다.
- **Model Init**: 언어 모델 초기화 및 가중치 관리는 `Dockerfile.model`을 통해 별도의 이미지로 관리됩니다.

### 📝 Pull Request 규칙
- **Template**: PR 생성 시 `.github/PULL_REQUEST_TEMPLATE.md`의 형식을 반드시 준수하여 변경 사항, 테스트 결과, 스크린샷 등을 상세히 기록합니다.
