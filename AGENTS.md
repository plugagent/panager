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
3. **Database**: `POSTGRES_PASSWORD` 및 `POSTGRES_PORT`를 설정합니다.
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

### Discord Direct Testing
실제 환경에서의 검증을 위해 다음 절차를 따릅니다:
1. 봇 실행: `make dev`
2. Discord DM 발송: 봇에게 직접 메시지를 보내 기능 작동 확인.
3. 로그 확인: 실시간 실행 세부 사항을 확인합니다.
   - 로컬 실행 시: 터미널 출력 확인.
   - Docker 실행 시: `make dev-logs` 사용.

---

## Coding Standards & Tool Development

### Python & Style
- **Imports**: Always include `from __future__ import annotations` at the top of every Python file.
- **Formatting**: Use `ruff` for linting and formatting.
- **Strict Typing**: **MANDATORY**: `Any` 사용 금지.
    - 노드 출력물은 `TypedDict` 사용.
    - 복잡한 구조체(예: `DiscoveredTool`, `PendingReflection`)는 Pydantic `BaseModel` 사용.
- **Async SDK Handling**: Google, GitHub 등 블로킹(Sync) SDK 호출 시 반드시 `asyncio.to_thread()`를 사용하여 이벤트 루프 중단을 방지하세요.
- **Paths**: 항상 프로젝트 루트를 기준으로 한 절대 경로를 사용하세요.

### <a name="tool-development-critical"></a>Tool Development (CRITICAL)
- **Location**: `src/panager/tools/`에 도메인별로 배치.
- **Decorator**: `@tool` 데코레이터 사용.
- **Metadata**: 모든 도구는 `@tool(..., metadata={"domain": "..."})`와 같이 도메인을 명시해야 합니다. 이는 시멘틱 검색 및 인증 라우팅에 사용됩니다.
- **Return Type**: **MANDATORY**: 모든 도구는 반드시 **JSON 형식의 문자열**을 반환해야 합니다.

---

## <a name="workflow--commits"></a>Workflow & Commits

### Git Workflow
- **Branching**: `dev` 브랜치에서 기능 브랜치를 생성하여 작업.
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) 준수.
  - **Subject**: **한국어** (예: `feat: 구글 캘린더 도구 추가`).
  - **Body**: **한국어** 상세 설명.

### Conventional Commit Types
- `feat`: 새로운 기능 추가
- `fix`: 버그 수정
- `docs`: 문서 수정
- `style`: 코드 의미에 영향을 주지 않는 변경 (포맷팅 등)
- `refactor`: 성능 개선이나 버그 수정을 포함하지 않는 코드 구조 변경
- `test`: 테스트 코드 추가 및 수정
- `chore`: 빌드 업무 수정, 패키지 매니저 설정 등

---

## Agent State Management

### LangGraph AgentState
- **Definition**: `src/panager/agent/state.py`에서 관리.
- **Message Handling**: `Annotated[list[AnyMessage], add_messages]`를 사용하여 대화 이력을 누적합니다.
- **Node Best Practices**:
    1. **멱등성(Idempotency)**: 노드가 에러 후 재시작되어도 안전하도록 설계하세요.
    2. **상태 정리**: `is_system_trigger`와 같은 일회성 플래그는 사용 후 즉시 클리어하세요.

### Persistence & Resumption
- **Thread IDs**: Discord 채널 ID와 연동하여 세션을 유지합니다.
- **Checkpointers**: `PostgresSaver`를 사용하여 상태를 영구 저장합니다.
- **Auto-Resumption**:
    1. 인증 인터럽트 발생 시 `auth_message_id`와 `auth_request_url`을 상태에 저장.
    2. OAuth 콜백 수신 후 `astream(None, ...)`을 호출하여 중단된 지점부터 즉시 재개.

---

## UX and Discord Interaction Standards

### 1. Single Message Policy
- 봇은 사용자 입력당 **하나의 메시지**만 남깁니다. 초기 "생각 중..." 메시지를 계속 **수정(Edit)**하여 최종 결과를 보여줍니다.

### 2. Step-by-Step Visibility
- 진행 상황을 실시간으로 업데이트하여 투명성을 높입니다.
  - `discovery`: "의도를 파악하고 있습니다..."
  - `agent`: "관련 도구를 검색하고 계획을 세우는 중입니다..."
  - `tool_executor`: "도구 실행 중: `{tool_name}`..."
  - `auth_interrupt`: "보안 인증이 필요합니다."

---

## Advanced Patterns

### Auth Interrupt & Resume
- **Mechanism**: 인증이 필요한 경우 LangGraph의 `interrupt()`를 사용합니다.
- **Single Message UX**: 저장된 `auth_message_id`를 사용하여 인증 링크 메시지를 결과 메시지로 자연스럽게 전환합니다.

### GitHub Push Reflection
- **Webhook**: 푸시 이벤트 수신 -> `PendingReflection` (Pydantic) 모델로 변환 -> 에이전트 작업 트리거.

---

## CI/CD & Deployment

### Infrastructure Configuration
- **Port Synchronization**: 배포 환경의 충돌 방지를 위해 `.env`의 `POSTGRES_PORT` 하나로 호스트 포트, 컨테이너 내부 포트(`PGPORT`), 앱 접속 포트를 모두 동기화합니다.

### GitHub Actions Pipeline
- **Dev Pipeline**: `dev` 브랜치 푸시 시 `Lint -> Test -> Build -> Deploy`가 자동 트리거됩니다.
- **Test DB**: CI 환경에서는 `pgvector`가 포함된 전용 PostgreSQL 컨테이너를 사용하여 실제 DB 통합 테스트를 수행합니다.

### Deployment Method
- **Security**: Tailscale을 통해 배포 서버에 보안 접속합니다.
- **Registry**: 빌드된 이미지는 `ghcr.io`에 저장되며, 서버에서 `docker compose pull`로 업데이트합니다.
