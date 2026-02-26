# 패니저 (Panager) 설계 문서

**날짜**: 2026-02-20
**상태**: 승인 완료

---

## 비전

Discord 1:1 DM을 통해 사용자와 대화하며, 행동 패턴을 학습하여 **사람보다 더 나은 매니저**가 되는 멀티-유저 SaaS AI 에이전트.

---

## 아키텍처

```
Discord User
    │  DM / 슬래시 커맨드
    ▼
discord.py (Bot)
    │
    ▼
LangGraph ReAct Agent
    ├── memory_tool      → PostgreSQL + pgvector
    ├── schedule_tool    → APScheduler + PostgreSQL
    └── google_task_tool → Google Tasks API (OAuth)

FastAPI (OAuth 서버)
    └── /auth/google/callback → google_tokens 저장
```

### 온보딩 플로우

```
첫 DM
  → users 테이블 자동 등록 + 환영 메시지
  → 구글 계정 연동 링크 전송
  → 브라우저에서 OAuth 승인
  → FastAPI 콜백 → google_tokens 저장
  → 연동 완료 DM 전송 → 대화 시작
```

### 핵심 데이터 흐름

1. DM 수신 → pgvector에서 유사 컨텍스트 검색 → 시스템 프롬프트 강화
2. LangGraph ReAct 루프 → Tool 호출 → 응답 생성 → DM 전송
3. 대화 요약 → pgvector 저장 (장기 기억 축적)
4. 발화에서 의도 감지 → 자동 알림 생성 (이벤트 드리븐)

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Python | 3.13 |
| Discord | `discord.py` |
| AI 에이전트 | `langgraph`, `langchain-openai` |
| 체크포인터 | `langgraph-checkpoint-postgres` |
| LLM | OpenCode Zen (`minimax-m2.5-free`, OpenAI Compatible, 환경변수로 교체 가능) |
| OAuth 서버 | `fastapi`, `uvicorn` |
| Google 연동 | `google-auth`, `google-auth-oauthlib`, `google-api-python-client` |
| DB | PostgreSQL 16 + `pgvector` |
| Async DB | `asyncpg` |
| 마이그레이션 | `alembic` |
| 스케줄러 | `APScheduler` (AsyncIOScheduler) |
| 임베딩 | `sentence-transformers` (`paraphrase-multilingual-mpnet-base-v2`, 768차원) |
| 설정 관리 | `pydantic-settings` |
| 타입 안전성 | `TypedDict` + `Pydantic BaseModel` |
| 로깅 | `structlog` (콘솔: ConsoleRenderer / 파일: JSON, 항상 동시) |
| 컨테이너 | Docker + Docker Compose |
| 패키지 관리 | `uv` |
| 테스트 | `pytest`, `pytest-asyncio` |

---

## DB 스키마

```sql
-- 사용자
CREATE TABLE users (
    user_id     BIGINT PRIMARY KEY,
    username    TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    profile     JSONB NOT NULL DEFAULT '{}'
);

-- Google OAuth 토큰
CREATE TABLE google_tokens (
    user_id       BIGINT PRIMARY KEY REFERENCES users(user_id),
    access_token  TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 알림
CREATE TABLE schedules (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     BIGINT NOT NULL REFERENCES users(user_id),
    message     TEXT NOT NULL,
    trigger_at  TIMESTAMPTZ NOT NULL,
    sent        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 벡터 메모리 (768차원)
CREATE TABLE memories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     BIGINT NOT NULL REFERENCES users(user_id),
    content     TEXT NOT NULL,
    embedding   VECTOR(768) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata    JSONB NOT NULL DEFAULT '{}'
);

-- 인덱스
CREATE INDEX ON schedules(user_id, sent, trigger_at);
CREATE INDEX ON memories(user_id);
CREATE INDEX ON memories USING hnsw (embedding vector_cosine_ops);
```

---

## AgentState

```python
class AgentState(TypedDict):
    user_id:        int                            # Discord Snowflake ID
    username:       str
    messages:       Annotated[list, add_messages]  # 대화 히스토리
    memory_context: str                            # pgvector 검색 결과
```

---

## Tools

```python
# memory_tool
class MemorySearchInput(BaseModel):
    query: str
    limit: int = 5

class MemorySaveInput(BaseModel):
    content: str

# schedule_tool
class ScheduleCreateInput(BaseModel):
    message: str
    trigger_at: datetime

class ScheduleCancelInput(BaseModel):
    schedule_id: UUID

# google_task_tool
class TaskCreateInput(BaseModel):
    title: str
    due_at: datetime | None = None

class TaskCompleteInput(BaseModel):
    task_id: str
```

---

## 프로젝트 구조

```
panager/
├── src/
│   └── panager/
│       ├── config.py             # Pydantic Settings
│       ├── logging.py            # structlog (콘솔 + 파일 동시)
│       ├── bot/
│       │   ├── client.py         # Discord 봇 진입점, 인텐트 설정, APScheduler 시작
│       │   └── handlers.py       # on_message DM 필터링, 슬래시 커맨드 등록
│       ├── api/
│       │   ├── main.py           # FastAPI 앱 초기화, 라우터 등록
│       │   └── auth.py           # /auth/google/callback 엔드포인트
│       ├── agent/
│       │   ├── graph.py          # LangGraph ReAct 그래프, 체크포인터 연결
│       │   └── state.py          # AgentState TypedDict
│       ├── memory/
│       │   ├── tool.py           # @tool: memory_search, memory_save
│       │   └── repository.py     # pgvector 저장/검색/삭제
│       ├── scheduler/
│       │   ├── tool.py           # @tool: schedule_create, schedule_cancel
│       │   └── runner.py         # APScheduler 초기화, 재시작 시 미발송 복구
│       ├── google/
│       │   ├── tool.py           # @tool: task_create, task_list, task_complete
│       │   ├── auth.py           # OAuth URL 생성, 토큰 갱신
│       │   └── repository.py     # google_tokens CRUD
│       └── db/
│           └── connection.py     # asyncpg 연결 풀 초기화/종료
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── tests/
│   ├── conftest.py               # pytest fixtures (테스트 DB, 봇 mock)
│   ├── memory/
│   │   ├── test_tool.py
│   │   └── test_repository.py
│   ├── scheduler/
│   │   ├── test_tool.py
│   │   └── test_runner.py
│   ├── google/
│   │   ├── test_tool.py
│   │   └── test_auth.py
│   └── agent/
│       └── test_graph.py
├── docs/plans/
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.test.yml
├── Dockerfile
├── .dockerignore
├── .env.example
├── alembic.ini
└── pyproject.toml
```

---

## 파일별 정의

### `config.py`

```python
class Settings(BaseSettings):
    # Discord
    discord_token: str

    # LLM (OpenCode Zen, OpenAI Compatible)
    llm_base_url: str
    llm_api_key: str
    llm_model: str = "minimax-m2.5-free"

    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int = 5432

    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    # 로그
    log_file_path: str
    log_max_bytes: int = 10_485_760  # 10MB
    log_backup_count: int = 5

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
```

### `logging.py`

- 콘솔 핸들러: `structlog.dev.ConsoleRenderer` (컬러, 가독성)
- 파일 핸들러: `structlog.processors.JSONRenderer` (구조화 JSON)
- 항상 두 핸들러 동시 활성화 (환경 무관)
- `RotatingFileHandler`: `log_max_bytes`, `log_backup_count` 설정값 사용

### `bot/client.py`

- `discord.Intents`: `message_content`, DM 메시지 활성화
- `PanagerBot(discord.Client)` 클래스
- `setup_hook`: DB 연결 풀 초기화, APScheduler 시작, 미발송 스케줄 복구, 슬래시 커맨드 등록
- `on_ready`: 봇 시작 완료 로그
- `close`: APScheduler 종료, DB 연결 풀 종료

### `bot/handlers.py`

- `on_message`: Guild 메시지 무시, DM만 처리, 봇 메시지 무시
- 신규 사용자: `users` 테이블 자동 등록 + 환영 메시지 + Google OAuth 링크 전송
- 기존 사용자: `AgentState` 구성 → LangGraph 에이전트 실행 → 응답 전송
- `/tasks`: Google Tasks 목록 조회 후 응답
- `/status`: 오늘의 요약 생성 후 응답

### `api/main.py`

- FastAPI 앱 초기화
- `lifespan`: DB 연결 풀 초기화/종료
- `/auth` 라우터 등록

### `api/auth.py`

- `GET /auth/google/login?user_id=...`: OAuth 인증 URL 생성 → 리다이렉트
- `GET /auth/google/callback`: code → token 교환 → `google_tokens` 저장 → Discord DM 전송

### `agent/graph.py`

- LangGraph `StateGraph(AgentState)` 정의
- 노드: `agent` (LLM 호출), `tools` (Tool 실행)
- `langgraph-checkpoint-postgres` 체크포인터 연결
- `thread_id` = `str(user_id)`로 사용자별 세션 독립

### `agent/state.py`

- `AgentState(TypedDict)`: `user_id`, `username`, `messages`, `memory_context`

### `memory/tool.py`

- `memory_search(query, limit)`: pgvector 유사도 검색
- `memory_save(content)`: 임베딩 생성 후 pgvector 저장

### `memory/repository.py`

- `save_memory(user_id, content, embedding)` → UUID
- `search_memories(user_id, embedding, limit)` → list[str]
- `delete_memory(user_id, memory_id)` → None

### `scheduler/tool.py`

- `schedule_create(message, trigger_at)`: APScheduler 등록 + DB 저장
- `schedule_cancel(schedule_id)`: APScheduler 취소 + DB 삭제

### `scheduler/runner.py`

- `AsyncIOScheduler` 초기화
- `restore_pending_schedules`: 재시작 시 `sent=False` 스케줄 복구
- `send_scheduled_dm`: DM 발송 → `sent=True` 업데이트, 실패 시 최대 3회 재시도

### `google/tool.py`

- `task_create(title, due_at)`: Google Tasks API로 할 일 생성
- `task_list()`: 할 일 목록 조회
- `task_complete(task_id)`: 할 일 완료 처리

### `google/auth.py`

- `get_auth_url(user_id)`: scope=tasks OAuth URL 생성
- `exchange_code(code, user_id)`: authorization code → tokens
- `refresh_access_token(user_id)`: refresh_token으로 access_token 갱신

### `google/repository.py`

- `save_tokens(user_id, tokens)` → None
- `get_tokens(user_id)` → GoogleTokens | None
- `update_access_token(user_id, access_token, expires_at)` → None

### `db/connection.py`

- `asyncpg.Pool` 싱글톤 관리
- `init_pool(dsn)`: min_size=2, max_size=10
- `close_pool()`: 연결 풀 종료
- `get_pool()`: 연결 풀 반환

---

## Dockerfile

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

WORKDIR /app

ENV HF_HOME=/app/.cache/huggingface
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN adduser --disabled-password --gecos "" panager

# 의존성만 먼저 설치 (레이어 캐시 최적화)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY src/ ./src/
COPY pyproject.toml uv.lock ./

# 프로젝트 설치
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# 임베딩 모델 사전 다운로드
RUN uv run python -c \
    "from sentence_transformers import SentenceTransformer; \
     SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

RUN chown -R panager:panager /app

USER panager

CMD ["uv", "run", "python", "-m", "panager.bot.client"]
```

### .dockerignore

```
.git/
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
logs/
docs/
```

---

## Docker Compose

### `docker-compose.yml`

```yaml
services:
  panager:
    build: .
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  api:
    build: .
    command: uv run uvicorn panager.api.main:app --host 0.0.0.0 --port 8000
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: pgvector/pgvector:pg16
    env_file: .env
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $POSTGRES_USER"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### `docker-compose.dev.yml`

```yaml
services:
  panager:
    volumes:
      - ./src:/app/src
      - ./logs:/app/logs
    command: uv run watchfiles "python -m panager.bot.client" src

  api:
    volumes:
      - ./src:/app/src
    command: uv run uvicorn panager.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### `docker-compose.test.yml`

```yaml
services:
  db_test:
    image: pgvector/pgvector:pg16
    env_file: .env.test
    ports:
      - "5432:5432"
    tmpfs:
      - /var/lib/postgresql/data
```

---

## 환경변수 (`.env.example`)

```
# Discord
DISCORD_TOKEN=

# LLM (OpenCode Zen, OpenAI Compatible)
LLM_BASE_URL=https://opencode.ai/zen/v1
LLM_API_KEY=
LLM_MODEL=minimax-m2.5-free

# PostgreSQL
POSTGRES_USER=panager
POSTGRES_PASSWORD=
POSTGRES_DB=panager
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# 로그
LOG_FILE_PATH=/app/logs/panager.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
```

---

## `pyproject.toml`

```toml
[project]
name = "panager"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "discord.py",
    "langgraph",
    "langgraph-checkpoint-postgres",
    "langchain-openai",
    "fastapi",
    "uvicorn",
    "asyncpg",
    "alembic",
    "apscheduler",
    "sentence-transformers",
    "pydantic-settings",
    "structlog",
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "watchfiles"]

[tool.uv.scripts]
bot = "python -m panager.bot.client"
api = "uvicorn panager.api.main:app --reload"
migrate = "alembic upgrade head"
test = "pytest"
```

---

## `alembic.ini`

```ini
[alembic]
script_location = alembic
# DSN은 alembic/env.py에서 환경변수로 주입
```

---

## 슬래시 커맨드

| 커맨드 | 설명 |
|--------|------|
| `/tasks` | Google Tasks 할 일 목록 조회 |
| `/status` | 오늘의 요약 |

추후 필요에 따라 확장.

---

## Git 전략

| 항목 | 결정 |
|------|------|
| 브랜치 | `main` + `dev` |
| 커밋 컨벤션 | Conventional Commits + 한글 |

```
feat: 메모리 툴 저장/검색 기능 추가
fix: 디스코드 rate limit 처리
docs: 패니저 설계 문서 추가
chore: docker-compose 설정 추가
```

---

## 멀티-유저 격리

- PostgreSQL 모든 테이블에 `user_id` (Discord Snowflake ID)
- 모든 쿼리에 `WHERE user_id = ?` 필터 강제
- pgvector 검색 시 `user_id` 메타데이터 필터링
- LangGraph `thread_id` = `str(user_id)`

---

## 에러 핸들링

| 시나리오 | 처리 방식 |
|---------|----------|
| LLM API 타임아웃/오류 | 최대 3회 재시도 후 사용자에게 에러 메시지 |
| Discord Rate Limit | exponential backoff, 발송 큐 |
| DB 연결 오류 | 에러 로깅, 사용자에게 알림 |
| 모호한 사용자 의도 | 에이전트가 확인 요청 |
| APScheduler 알림 실패 | 최대 3회 재시도, PostgreSQL에 실패 기록 |

---

## 테스트 전략

- `pytest` + `pytest-asyncio`
- Discord 봇 모킹: `unittest.mock`
- 각 Tool 함수 단위 테스트
- LangGraph 그래프 통합 테스트 (LLM mock)
- 테스트 DB: `docker-compose.test.yml` (pgvector 포함, tmpfs로 자동 삭제)
