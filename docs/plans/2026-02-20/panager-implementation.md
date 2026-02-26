# 패니저 (Panager) 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Discord 1:1 DM 기반 멀티-유저 SaaS AI 매니저 에이전트를 구현한다.

**Architecture:** discord.py로 DM을 수신하여 LangGraph ReAct 에이전트로 처리한다. 에이전트는 memory_tool(pgvector), schedule_tool(APScheduler), google_task_tool(Google Tasks API)을 통해 사용자를 지원한다. FastAPI 서버가 Google OAuth 콜백을 처리한다.

**Tech Stack:** Python 3.13, discord.py, langgraph, langgraph-checkpoint-postgres, langchain-openai, fastapi, asyncpg, alembic, APScheduler, sentence-transformers, pydantic-settings, structlog, google-auth, uv, pytest, Docker + Docker Compose (pgvector/pgvector:pg16, ghcr.io/astral-sh/uv:python3.13-trixie-slim)

---

## Task 1: 프로젝트 초기 설정

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.dockerignore`
- Create: `.gitignore`

**Step 1: `pyproject.toml` 작성**

```toml
[project]
name = "panager"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "discord.py>=2.4.0",
    "langgraph>=0.2.0",
    "langgraph-checkpoint-postgres>=2.0.0",
    "langchain-openai>=0.2.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "apscheduler>=3.10.0",
    "sentence-transformers>=3.3.0",
    "pydantic-settings>=2.6.0",
    "structlog>=24.4.0",
    "google-auth>=2.36.0",
    "google-auth-oauthlib>=1.2.0",
    "google-api-python-client>=2.154.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "watchfiles>=1.0.0",
]

[tool.uv.scripts]
bot = "python -m panager.bot.client"
api = "uvicorn panager.api.main:app --reload"
migrate = "alembic upgrade head"
test = "pytest"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Step 2: uv 초기화 및 lockfile 생성**

```bash
uv sync
```

예상 출력: `Resolved N packages` 후 `uv.lock` 생성

**Step 3: `.env.example` 작성**

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

**Step 4: `.dockerignore` 작성**

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

**Step 5: `.gitignore` 작성**

```
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
logs/
*.egg-info/
dist/
.cache/
```

**Step 6: 커밋**

```bash
git checkout -b dev
git add pyproject.toml uv.lock .env.example .dockerignore .gitignore
git commit -m "chore: 프로젝트 초기 설정"
```

---

## Task 2: 패키지 구조 및 설정 관리

**Files:**
- Create: `src/panager/__init__.py`
- Create: `src/panager/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: 패키지 디렉토리 생성**

```bash
mkdir -p src/panager/bot src/panager/api src/panager/agent \
         src/panager/memory src/panager/scheduler \
         src/panager/google src/panager/db \
         tests/memory tests/scheduler tests/google tests/agent
touch src/panager/__init__.py \
      src/panager/bot/__init__.py \
      src/panager/api/__init__.py \
      src/panager/agent/__init__.py \
      src/panager/memory/__init__.py \
      src/panager/scheduler/__init__.py \
      src/panager/google/__init__.py \
      src/panager/db/__init__.py \
      tests/__init__.py \
      tests/memory/__init__.py \
      tests/scheduler/__init__.py \
      tests/google/__init__.py \
      tests/agent/__init__.py
```

**Step 2: 실패하는 테스트 작성**

```python
# tests/test_config.py
def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "test_token")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com")
    monkeypatch.setenv("LLM_API_KEY", "test_key")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost/callback")
    monkeypatch.setenv("LOG_FILE_PATH", "/tmp/test.log")

    from panager.config import Settings
    settings = Settings()
    assert settings.discord_token == "test_token"
    assert settings.llm_model == "minimax-m2.5-free"
    assert settings.postgres_port == 5432

def test_postgres_dsn_property(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "t")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("POSTGRES_USER", "panager")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "panager")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "cs")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost/callback")
    monkeypatch.setenv("LOG_FILE_PATH", "/tmp/test.log")

    from panager.config import Settings
    settings = Settings()
    assert "panager:secret@localhost:5432/panager" in settings.postgres_dsn
```

**Step 3: 테스트 실패 확인**

```bash
uv run pytest tests/test_config.py -v
```

예상: `ModuleNotFoundError: No module named 'panager.config'`

**Step 4: `src/panager/config.py` 구현**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Discord
    discord_token: str

    # LLM
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
    log_max_bytes: int = 10_485_760
    log_backup_count: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn_asyncpg(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
```

**Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/test_config.py -v
```

예상: `2 passed`

**Step 6: 커밋**

```bash
git add src/ tests/
git commit -m "feat: 패키지 구조 및 설정 관리 추가"
```

---

## Task 3: 로깅 설정

**Files:**
- Create: `src/panager/logging.py`
- Create: `tests/test_logging.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_logging.py
import logging
from unittest.mock import MagicMock

def test_configure_logging_adds_two_handlers():
    mock_settings = MagicMock()
    mock_settings.log_file_path = "/tmp/test_panager.log"
    mock_settings.log_max_bytes = 1_048_576
    mock_settings.log_backup_count = 3

    from panager.logging import configure_logging
    configure_logging(mock_settings)

    root_logger = logging.getLogger()
    handler_types = [type(h).__name__ for h in root_logger.handlers]
    assert "StreamHandler" in handler_types
    assert "RotatingFileHandler" in handler_types
```

**Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_logging.py -v
```

예상: `ModuleNotFoundError: No module named 'panager.logging'`

**Step 3: `src/panager/logging.py` 구현**

```python
import logging
import logging.handlers

import structlog


def configure_logging(settings) -> None:
    console_handler = logging.StreamHandler()
    file_handler = logging.handlers.RotatingFileHandler(
        filename=settings.log_file_path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )

    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(),
    )
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
    )

    console_handler.setFormatter(console_formatter)
    file_handler.setFormatter(file_formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)
```

**Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_logging.py -v
```

예상: `1 passed`

**Step 5: 커밋**

```bash
git add src/panager/logging.py tests/test_logging.py
git commit -m "feat: structlog 기반 로깅 설정 추가"
```

---

## Task 4: DB 연결 풀

**Files:**
- Create: `src/panager/db/connection.py`
- Create: `tests/conftest.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_db_connection.py
import pytest

@pytest.mark.asyncio
async def test_init_and_close_pool():
    import os
    dsn = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://panager:panager@localhost:5432/panager"
    )
    from panager.db.connection import init_pool, close_pool, get_pool
    await init_pool(dsn)
    pool = get_pool()
    assert pool is not None

    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    assert result == 1

    await close_pool()
```

**Step 2: 테스트 DB 실행**

```bash
docker compose -f docker-compose.test.yml up -d
```

예상: `pgvector/pgvector:pg16` 컨테이너 시작

**Step 3: 테스트 실패 확인**

```bash
uv run pytest tests/test_db_connection.py -v
```

예상: `ModuleNotFoundError: No module named 'panager.db.connection'`

**Step 4: `src/panager/db/connection.py` 구현**

```python
from __future__ import annotations

import asyncpg

_pool: asyncpg.Pool | None = None


async def init_pool(dsn: str, min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized. Call init_pool() first.")
    return _pool
```

**Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/test_db_connection.py -v
```

예상: `1 passed`

**Step 6: 커밋**

```bash
git add src/panager/db/connection.py tests/test_db_connection.py
git commit -m "feat: asyncpg 연결 풀 추가"
```

---

## Task 5: Alembic 마이그레이션 설정

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial_schema.py`

**Step 1: Alembic 초기화**

```bash
uv run alembic init alembic
```

**Step 2: `alembic/env.py` 수정**

```python
import os
from logging.config import fileConfig
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 환경변수에서 DSN 주입
dsn = (
    f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ.get('POSTGRES_PORT', '5432')}"
    f"/{os.environ['POSTGRES_DB']}"
)
config.set_main_option("sqlalchemy.url", dsn)


def run_migrations_offline() -> None:
    context.configure(url=dsn, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config, pool
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 3: 초기 스키마 마이그레이션 생성**

```bash
uv run alembic revision --autogenerate -m "initial_schema"
```

**Step 4: `alembic/versions/0001_initial_schema.py` 내용 확인 후 수동 작성**

```python
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger, primary_key=True),
        sa.Column("username", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("profile", sa.JSON, server_default="{}", nullable=False),
    )

    op.create_table(
        "google_tokens",
        sa.Column("user_id", sa.BigInteger,
                  sa.ForeignKey("users.user_id"), primary_key=True),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "schedules",
        sa.Column("id", sa.UUID, primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.BigInteger,
                  sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("trigger_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_schedules_user_sent_trigger",
                    "schedules", ["user_id", "sent", "trigger_at"])

    op.create_table(
        "memories",
        sa.Column("id", sa.UUID, primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.BigInteger,
                  sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON, server_default="{}", nullable=False),
    )
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.execute(
        "CREATE INDEX ix_memories_embedding ON memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("memories")
    op.drop_table("schedules")
    op.drop_table("google_tokens")
    op.drop_table("users")
```

**Step 5: 마이그레이션 실행 확인 (테스트 DB)**

```bash
POSTGRES_USER=panager POSTGRES_PASSWORD=panager \
POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=panager \
uv run alembic upgrade head
```

예상: `Running upgrade -> 0001, initial_schema`

**Step 6: 커밋**

```bash
git add alembic/ alembic.ini
git commit -m "chore: alembic 마이그레이션 초기 스키마 추가"
```

---

## Task 6: 메모리 레포지토리

**Files:**
- Create: `src/panager/memory/repository.py`
- Create: `tests/memory/test_repository.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/memory/test_repository.py
import pytest
from uuid import UUID

@pytest.fixture(autouse=True)
async def setup_db():
    import os
    from panager.db.connection import init_pool, close_pool
    dsn = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://panager:panager@localhost:5432/panager"
    )
    await init_pool(dsn)
    # 테스트용 사용자 생성
    from panager.db.connection import get_pool
    async with get_pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            999999, "test_user"
        )
    yield
    async with get_pool().acquire() as conn:
        await conn.execute("DELETE FROM memories WHERE user_id = $1", 999999)
        await conn.execute("DELETE FROM users WHERE user_id = $1", 999999)
    await close_pool()

@pytest.mark.asyncio
async def test_save_and_search_memory():
    from panager.memory.repository import save_memory, search_memories

    embedding = [0.1] * 768
    memory_id = await save_memory(999999, "오늘 회의 참석", embedding)
    assert isinstance(memory_id, UUID)

    results = await search_memories(999999, embedding, limit=5)
    assert len(results) >= 1
    assert "오늘 회의 참석" in results
```

**Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/memory/test_repository.py -v
```

예상: `ModuleNotFoundError: No module named 'panager.memory.repository'`

**Step 3: `src/panager/memory/repository.py` 구현**

```python
from __future__ import annotations

from uuid import UUID

from panager.db.connection import get_pool


async def save_memory(
    user_id: int, content: str, embedding: list[float]
) -> UUID:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO memories (user_id, content, embedding)
            VALUES ($1, $2, $3::vector)
            RETURNING id
            """,
            user_id,
            content,
            str(embedding),
        )
        return UUID(str(row["id"]))


async def search_memories(
    user_id: int, embedding: list[float], limit: int = 5
) -> list[str]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT content
            FROM memories
            WHERE user_id = $1
            ORDER BY embedding <=> $2::vector
            LIMIT $3
            """,
            user_id,
            str(embedding),
            limit,
        )
        return [row["content"] for row in rows]


async def delete_memory(user_id: int, memory_id: UUID) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM memories WHERE user_id = $1 AND id = $2",
            user_id,
            memory_id,
        )
```

**Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/memory/test_repository.py -v
```

예상: `1 passed`

**Step 5: 커밋**

```bash
git add src/panager/memory/repository.py tests/memory/test_repository.py
git commit -m "feat: pgvector 메모리 레포지토리 추가"
```

---

## Task 7: 메모리 Tool

**Files:**
- Create: `src/panager/memory/tool.py`
- Create: `tests/memory/test_tool.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/memory/test_tool.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_memory_save_tool():
    with patch("panager.memory.tool.save_memory", new_callable=AsyncMock) as mock_save, \
         patch("panager.memory.tool._get_embedding", return_value=[0.1] * 768):
        mock_save.return_value = "test-uuid"

        from panager.memory.tool import memory_save
        result = await memory_save.ainvoke(
            {"content": "오늘 회의 참석", "user_id": 123}
        )
        assert "저장" in result
        mock_save.assert_called_once()

@pytest.mark.asyncio
async def test_memory_search_tool():
    with patch("panager.memory.tool.search_memories", new_callable=AsyncMock) as mock_search, \
         patch("panager.memory.tool._get_embedding", return_value=[0.1] * 768):
        mock_search.return_value = ["오늘 회의 참석"]

        from panager.memory.tool import memory_search
        result = await memory_search.ainvoke(
            {"query": "회의", "user_id": 123, "limit": 5}
        )
        assert "오늘 회의 참석" in result
```

**Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/memory/test_tool.py -v
```

**Step 3: `src/panager/memory/tool.py` 구현**

```python
from __future__ import annotations

from pydantic import BaseModel
from langchain_core.tools import tool
from sentence_transformers import SentenceTransformer

from panager.memory.repository import save_memory, search_memories

_model: SentenceTransformer | None = None


def _get_embedding(text: str) -> list[float]:
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    return _model.encode(text).tolist()


class MemorySaveInput(BaseModel):
    content: str
    user_id: int


class MemorySearchInput(BaseModel):
    query: str
    user_id: int
    limit: int = 5


@tool(args_schema=MemorySaveInput)
async def memory_save(content: str, user_id: int) -> str:
    """중요한 내용을 장기 메모리에 저장합니다."""
    embedding = _get_embedding(content)
    await save_memory(user_id, content, embedding)
    return f"메모리에 저장했습니다: {content[:50]}"


@tool(args_schema=MemorySearchInput)
async def memory_search(query: str, user_id: int, limit: int = 5) -> str:
    """사용자의 과거 대화/패턴에서 관련 내용을 검색합니다."""
    embedding = _get_embedding(query)
    results = await search_memories(user_id, embedding, limit)
    if not results:
        return "관련 메모리가 없습니다."
    return "\n".join(f"- {r}" for r in results)
```

**Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/memory/test_tool.py -v
```

예상: `2 passed`

**Step 5: 커밋**

```bash
git add src/panager/memory/tool.py tests/memory/test_tool.py
git commit -m "feat: 메모리 LangGraph Tool 추가"
```

---

## Task 8: 스케줄러 레포지토리 및 Runner

**Files:**
- Create: `src/panager/scheduler/runner.py`
- Create: `tests/scheduler/test_runner.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/scheduler/test_runner.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

@pytest.mark.asyncio
async def test_restore_pending_schedules():
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    future_time = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_conn.fetch.return_value = [
        {"id": "uuid-1", "user_id": 123, "message": "테스트 알림", "trigger_at": future_time}
    ]

    mock_scheduler = MagicMock()
    mock_bot = MagicMock()

    with patch("panager.scheduler.runner.get_pool", return_value=mock_pool), \
         patch("panager.scheduler.runner._scheduler", mock_scheduler):
        from panager.scheduler.runner import restore_pending_schedules
        await restore_pending_schedules(mock_bot)
        mock_scheduler.add_job.assert_called_once()
```

**Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/scheduler/test_runner.py -v
```

**Step 3: `src/panager/scheduler/runner.py` 구현**

```python
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from panager.db.connection import get_pool

log = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler = AsyncIOScheduler()


def get_scheduler() -> AsyncIOScheduler:
    return _scheduler


async def send_scheduled_dm(
    bot,
    user_id: int,
    schedule_id: str,
    message: str,
    retry: int = 0,
) -> None:
    try:
        user = await bot.fetch_user(user_id)
        await user.send(message)
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE schedules SET sent = TRUE WHERE id = $1",
                UUID(schedule_id),
            )
        log.info("알림 발송 완료", user_id=user_id, schedule_id=schedule_id)
    except Exception as e:
        if retry < 3:
            log.warning("알림 발송 실패, 재시도", retry=retry, error=str(e))
            await asyncio.sleep(2 ** retry)
            await send_scheduled_dm(bot, user_id, schedule_id, message, retry + 1)
        else:
            log.error("알림 발송 최대 재시도 초과", schedule_id=schedule_id)


async def restore_pending_schedules(bot) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, message, trigger_at
            FROM schedules
            WHERE sent = FALSE AND trigger_at > NOW()
            """
        )
    for row in rows:
        _scheduler.add_job(
            send_scheduled_dm,
            "date",
            run_date=row["trigger_at"],
            args=[bot, row["user_id"], str(row["id"]), row["message"]],
            id=str(row["id"]),
            replace_existing=True,
        )
    log.info("미발송 스케줄 복구 완료", count=len(rows))
```

**Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/scheduler/test_runner.py -v
```

예상: `1 passed`

**Step 5: 커밋**

```bash
git add src/panager/scheduler/runner.py tests/scheduler/test_runner.py
git commit -m "feat: APScheduler 러너 및 재시작 복구 로직 추가"
```

---

## Task 9: 스케줄러 Tool

**Files:**
- Create: `src/panager/scheduler/tool.py`
- Create: `tests/scheduler/test_tool.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/scheduler/test_tool.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4

@pytest.mark.asyncio
async def test_schedule_create_tool():
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_conn.fetchval.return_value = uuid4()

    mock_scheduler = MagicMock()
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)

    with patch("panager.scheduler.tool.get_pool", return_value=mock_pool), \
         patch("panager.scheduler.tool.get_scheduler", return_value=mock_scheduler):
        from panager.scheduler.tool import schedule_create
        result = await schedule_create.ainvoke({
            "message": "회의 알림",
            "trigger_at": future_time.isoformat(),
            "user_id": 123,
        })
        assert "예약" in result
        mock_scheduler.add_job.assert_called_once()
```

**Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/scheduler/test_tool.py -v
```

**Step 3: `src/panager/scheduler/tool.py` 구현**

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from langchain_core.tools import tool
from pydantic import BaseModel

from panager.db.connection import get_pool
from panager.scheduler.runner import get_scheduler, send_scheduled_dm


class ScheduleCreateInput(BaseModel):
    message: str
    trigger_at: str  # ISO 8601 형식
    user_id: int


class ScheduleCancelInput(BaseModel):
    schedule_id: str
    user_id: int


@tool(args_schema=ScheduleCreateInput)
async def schedule_create(message: str, trigger_at: str, user_id: int) -> str:
    """지정한 시간에 사용자에게 DM 알림을 예약합니다."""
    trigger_dt = datetime.fromisoformat(trigger_at)
    pool = get_pool()
    async with pool.acquire() as conn:
        schedule_id = await conn.fetchval(
            """
            INSERT INTO schedules (user_id, message, trigger_at)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            user_id,
            message,
            trigger_dt,
        )

    scheduler = get_scheduler()
    scheduler.add_job(
        send_scheduled_dm,
        "date",
        run_date=trigger_dt,
        args=[None, user_id, str(schedule_id), message],
        id=str(schedule_id),
        replace_existing=True,
    )
    return f"알림이 예약되었습니다: {trigger_at}에 '{message}'"


@tool(args_schema=ScheduleCancelInput)
async def schedule_cancel(schedule_id: str, user_id: int) -> str:
    """예약된 알림을 취소합니다."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM schedules WHERE id = $1 AND user_id = $2",
            UUID(schedule_id),
            user_id,
        )
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(schedule_id)
    except Exception:
        pass
    return f"알림이 취소되었습니다: {schedule_id}"
```

**Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/scheduler/test_tool.py -v
```

예상: `1 passed`

**Step 5: 커밋**

```bash
git add src/panager/scheduler/tool.py tests/scheduler/test_tool.py
git commit -m "feat: 스케줄러 LangGraph Tool 추가"
```

---

## Task 10: Google OAuth 및 레포지토리

**Files:**
- Create: `src/panager/google/auth.py`
- Create: `src/panager/google/repository.py`
- Create: `tests/google/test_auth.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/google/test_auth.py
import pytest
from unittest.mock import patch, MagicMock

def test_get_auth_url():
    from panager.config import Settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.google_client_id = "test_client_id"
    mock_settings.google_client_secret = "test_secret"
    mock_settings.google_redirect_uri = "http://localhost/callback"

    with patch("panager.google.auth.get_settings", return_value=mock_settings):
        from panager.google.auth import get_auth_url
        url = get_auth_url(user_id=123)
        assert "accounts.google.com" in url
        assert "tasks" in url
        assert "123" in url
```

**Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/google/test_auth.py -v
```

**Step 3: `src/panager/google/auth.py` 구현**

```python
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from functools import lru_cache

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from panager.config import Settings

SCOPES = ["https://www.googleapis.com/auth/tasks"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _make_flow(settings: Settings) -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )


def get_auth_url(user_id: int) -> str:
    settings = get_settings()
    flow = _make_flow(settings)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=str(user_id),
        prompt="consent",
    )
    return auth_url


async def exchange_code(code: str, user_id: int) -> dict:
    settings = get_settings()
    flow = _make_flow(settings)
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=3600),
    }


async def refresh_access_token(refresh_token: str) -> tuple[str, datetime]:
    settings = get_settings()
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    creds.refresh(Request())
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
    return creds.token, expires_at
```

**Step 4: `src/panager/google/repository.py` 구현**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from panager.db.connection import get_pool


@dataclass
class GoogleTokens:
    user_id: int
    access_token: str
    refresh_token: str
    expires_at: datetime


async def save_tokens(user_id: int, tokens: dict) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO google_tokens (user_id, access_token, refresh_token, expires_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
            SET access_token = $2, refresh_token = $3,
                expires_at = $4, updated_at = NOW()
            """,
            user_id,
            tokens["access_token"],
            tokens["refresh_token"],
            tokens["expires_at"],
        )


async def get_tokens(user_id: int) -> GoogleTokens | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM google_tokens WHERE user_id = $1", user_id
        )
    if not row:
        return None
    return GoogleTokens(
        user_id=row["user_id"],
        access_token=row["access_token"],
        refresh_token=row["refresh_token"],
        expires_at=row["expires_at"],
    )


async def update_access_token(
    user_id: int, access_token: str, expires_at: datetime
) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE google_tokens
            SET access_token = $2, expires_at = $3, updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
            access_token,
            expires_at,
        )
```

**Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/google/test_auth.py -v
```

예상: `1 passed`

**Step 6: 커밋**

```bash
git add src/panager/google/ tests/google/
git commit -m "feat: Google OAuth 인증 및 토큰 레포지토리 추가"
```

---

## Task 11: Google Tasks Tool

**Files:**
- Create: `src/panager/google/tool.py`
- Create: `tests/google/test_tool.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/google/test_tool.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_task_list_tool():
    mock_tokens = MagicMock()
    mock_tokens.access_token = "test_token"
    mock_tokens.expires_at = datetime.now(timezone.utc).replace(
        year=2099
    )

    mock_service = MagicMock()
    mock_service.tasks.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "1", "title": "테스트 할 일", "status": "needsAction"}]
    }

    with patch("panager.google.tool.get_tokens", new_callable=AsyncMock,
               return_value=mock_tokens), \
         patch("panager.google.tool._build_service", return_value=mock_service):
        from panager.google.tool import task_list
        result = await task_list.ainvoke({"user_id": 123})
        assert "테스트 할 일" in result
```

**Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/google/test_tool.py -v
```

**Step 3: `src/panager/google/tool.py` 구현**

```python
from __future__ import annotations

from datetime import datetime, timezone

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from langchain_core.tools import tool
from pydantic import BaseModel

from panager.google.repository import get_tokens, update_access_token
from panager.google.auth import refresh_access_token


async def _get_valid_credentials(user_id: int) -> Credentials:
    tokens = await get_tokens(user_id)
    if not tokens:
        raise ValueError("Google 계정이 연동되지 않았습니다. /auth 명령으로 연동해주세요.")

    if tokens.expires_at <= datetime.now(timezone.utc):
        new_token, new_expires = await refresh_access_token(tokens.refresh_token)
        await update_access_token(user_id, new_token, new_expires)
        tokens.access_token = new_token

    return Credentials(token=tokens.access_token)


def _build_service(creds: Credentials):
    return build("tasks", "v1", credentials=creds)


class TaskCreateInput(BaseModel):
    title: str
    user_id: int
    due_at: str | None = None


class TaskCompleteInput(BaseModel):
    task_id: str
    user_id: int


class TaskListInput(BaseModel):
    user_id: int


@tool(args_schema=TaskListInput)
async def task_list(user_id: int) -> str:
    """Google Tasks의 할 일 목록을 조회합니다."""
    creds = await _get_valid_credentials(user_id)
    service = _build_service(creds)
    result = service.tasks().list(tasklist="@default").execute()
    items = result.get("items", [])
    if not items:
        return "할 일이 없습니다."
    return "\n".join(
        f"- [{item['id']}] {item['title']}" for item in items
        if item.get("status") == "needsAction"
    )


@tool(args_schema=TaskCreateInput)
async def task_create(title: str, user_id: int, due_at: str | None = None) -> str:
    """Google Tasks에 새 할 일을 추가합니다."""
    creds = await _get_valid_credentials(user_id)
    service = _build_service(creds)
    body = {"title": title}
    if due_at:
        body["due"] = due_at
    service.tasks().insert(tasklist="@default", body=body).execute()
    return f"할 일이 추가되었습니다: {title}"


@tool(args_schema=TaskCompleteInput)
async def task_complete(task_id: str, user_id: int) -> str:
    """Google Tasks의 할 일을 완료 처리합니다."""
    creds = await _get_valid_credentials(user_id)
    service = _build_service(creds)
    service.tasks().patch(
        tasklist="@default", task=task_id, body={"status": "completed"}
    ).execute()
    return f"할 일이 완료 처리되었습니다: {task_id}"
```

**Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/google/test_tool.py -v
```

예상: `1 passed`

**Step 5: 커밋**

```bash
git add src/panager/google/tool.py tests/google/test_tool.py
git commit -m "feat: Google Tasks LangGraph Tool 추가"
```

---

## Task 12: LangGraph 에이전트 그래프

**Files:**
- Create: `src/panager/agent/state.py`
- Create: `src/panager/agent/graph.py`
- Create: `tests/agent/test_graph.py`

**Step 1: `src/panager/agent/state.py` 작성**

```python
from __future__ import annotations

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    user_id: int
    username: str
    messages: Annotated[list, add_messages]
    memory_context: str
```

**Step 2: 실패하는 테스트 작성**

```python
# tests/agent/test_graph.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_graph_builds_successfully():
    mock_checkpointer = MagicMock()

    with patch("panager.agent.graph.PostgresSaver", return_value=mock_checkpointer):
        from panager.agent.graph import build_graph
        graph = build_graph(mock_checkpointer)
        assert graph is not None


@pytest.mark.asyncio
async def test_graph_processes_message():
    from langchain_core.messages import HumanMessage, AIMessage
    mock_checkpointer = MagicMock()
    mock_llm_response = AIMessage(content="안녕하세요!")

    with patch("panager.agent.graph.PostgresSaver", return_value=mock_checkpointer), \
         patch("panager.agent.graph._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_get_llm.return_value = mock_llm

        from panager.agent.graph import build_graph
        graph = build_graph(mock_checkpointer)
        assert graph is not None
```

**Step 3: 테스트 실패 확인**

```bash
uv run pytest tests/agent/test_graph.py -v
```

**Step 4: `src/panager/agent/graph.py` 구현**

```python
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from panager.agent.state import AgentState
from panager.config import Settings
from panager.memory.tool import memory_save, memory_search
from panager.scheduler.tool import schedule_create, schedule_cancel
from panager.google.tool import task_create, task_list, task_complete

TOOLS = [memory_save, memory_search, schedule_create, schedule_cancel,
         task_create, task_list, task_complete]


@lru_cache
def _get_settings() -> Settings:
    return Settings()


def _get_llm() -> ChatOpenAI:
    settings = _get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )


def _agent_node(state: AgentState) -> dict:
    llm = _get_llm().bind_tools(TOOLS)
    system_prompt = (
        f"당신은 {state['username']}의 개인 매니저 패니저입니다. "
        "사용자의 할 일, 일정, 메모리를 관리하고 적극적으로 도와주세요.\n\n"
        f"관련 메모리:\n{state.get('memory_context', '없음')}"
    )
    from langchain_core.messages import SystemMessage
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def _should_continue(state: AgentState) -> Literal["tools", END]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_graph(checkpointer) -> object:
    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)
```

**Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/agent/test_graph.py -v
```

예상: `2 passed`

**Step 6: 커밋**

```bash
git add src/panager/agent/ tests/agent/
git commit -m "feat: LangGraph ReAct 에이전트 그래프 추가"
```

---

## Task 13: FastAPI OAuth 서버

**Files:**
- Create: `src/panager/api/main.py`
- Create: `src/panager/api/auth.py`

**Step 1: `src/panager/api/auth.py` 작성**

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from panager.google.auth import exchange_code, get_auth_url
from panager.google.repository import save_tokens

router = APIRouter()


@router.get("/google/login")
async def google_login(user_id: int):
    url = get_auth_url(user_id)
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(code: str, state: str):
    try:
        user_id = int(state)
        tokens = await exchange_code(code, user_id)
        await save_tokens(user_id, tokens)
        return {"message": "Google 계정 연동이 완료되었습니다. Discord로 돌아가세요."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Step 2: `src/panager/api/main.py` 작성**

```python
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from panager.api.auth import router as auth_router
from panager.config import Settings
from panager.db.connection import close_pool, init_pool

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool(settings.postgres_dsn_asyncpg)
    yield
    await close_pool()


app = FastAPI(title="Panager API", lifespan=lifespan)
app.include_router(auth_router, prefix="/auth")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 3: 커밋**

```bash
git add src/panager/api/
git commit -m "feat: FastAPI OAuth 서버 추가"
```

---

## Task 14: Discord 봇

**Files:**
- Create: `src/panager/bot/client.py`
- Create: `src/panager/bot/handlers.py`

**Step 1: `src/panager/bot/handlers.py` 작성**

```python
from __future__ import annotations

import logging

import discord
from discord import app_commands

from panager.config import Settings
from panager.db.connection import get_pool

log = logging.getLogger(__name__)
settings = Settings()

WELCOME_MESSAGE = (
    "안녕하세요! 저는 패니저입니다. 당신의 개인 매니저가 되겠습니다.\n"
    "먼저 Google 계정을 연동해주세요: {auth_url}"
)


async def handle_dm(message: discord.Message, bot, graph) -> None:
    user_id = message.author.id
    pool = get_pool()

    # 신규 사용자 등록
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT user_id FROM users WHERE user_id = $1", user_id
        )
        if not existing:
            await conn.execute(
                "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                user_id,
                str(message.author),
            )
            auth_url = f"http://localhost:8000/auth/google/login?user_id={user_id}"
            await message.channel.send(
                WELCOME_MESSAGE.format(auth_url=auth_url)
            )
            return

    # 에이전트 실행
    from langchain_core.messages import HumanMessage
    from panager.agent.state import AgentState

    config = {"configurable": {"thread_id": str(user_id)}}
    state: AgentState = {
        "user_id": user_id,
        "username": str(message.author),
        "messages": [HumanMessage(content=message.content)],
        "memory_context": "",
    }

    async with message.channel.typing():
        result = await graph.ainvoke(state, config=config)
        response = result["messages"][-1].content
        await message.channel.send(response)


def register_commands(bot, tree: app_commands.CommandTree) -> None:
    @tree.command(name="tasks", description="Google Tasks 할 일 목록 조회")
    async def tasks_command(interaction: discord.Interaction):
        await interaction.response.defer()
        from panager.google.tool import task_list
        result = await task_list.ainvoke({"user_id": interaction.user.id})
        await interaction.followup.send(result)

    @tree.command(name="status", description="오늘의 요약")
    async def status_command(interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.followup.send("오늘의 요약 기능은 준비 중입니다.")
```

**Step 2: `src/panager/bot/client.py` 작성**

```python
from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from panager.agent.graph import build_graph
from panager.bot.handlers import handle_dm, register_commands
from panager.config import Settings
from panager.db.connection import close_pool, init_pool
from panager.logging import configure_logging
from panager.scheduler.runner import get_scheduler, restore_pending_schedules

log = logging.getLogger(__name__)
settings = Settings()
configure_logging(settings)


class PanagerBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.graph = None

    async def setup_hook(self) -> None:
        await init_pool(settings.postgres_dsn_asyncpg)

        async with AsyncPostgresSaver.from_conn_string(
            settings.postgres_dsn_asyncpg
        ) as checkpointer:
            await checkpointer.setup()
            self.graph = build_graph(checkpointer)

        register_commands(self, self.tree)
        await self.tree.sync()

        scheduler = get_scheduler()
        scheduler.start()
        await restore_pending_schedules(self)
        log.info("봇 설정 완료")

    async def on_ready(self) -> None:
        log.info("봇 시작 완료", user=str(self.user))

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.DMChannel):
            return
        await handle_dm(message, self, self.graph)

    async def close(self) -> None:
        scheduler = get_scheduler()
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await close_pool()
        await super().close()


async def main() -> None:
    bot = PanagerBot()
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 3: 커밋**

```bash
git add src/panager/bot/
git commit -m "feat: Discord 봇 클라이언트 및 핸들러 추가"
```

---

## Task 15: Docker 설정

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `docker-compose.dev.yml`
- Create: `docker-compose.test.yml`

**Step 1: `Dockerfile` 작성**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

WORKDIR /app

ENV HF_HOME=/app/.cache/huggingface
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN adduser --disabled-password --gecos "" panager

# 의존성 설치 (레이어 캐시 최적화)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY src/ ./src/
COPY pyproject.toml uv.lock ./

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

**Step 2: `docker-compose.yml` 작성**

```yaml
services:
  panager:
    build: .
    env_file: .env
    volumes:
      - ./logs:/app/logs
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

**Step 3: `docker-compose.dev.yml` 작성**

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

**Step 4: `docker-compose.test.yml` 작성**

```yaml
services:
  db_test:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: panager
      POSTGRES_PASSWORD: panager
      POSTGRES_DB: panager
    ports:
      - "5432:5432"
    tmpfs:
      - /var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U panager"]
      interval: 5s
      timeout: 5s
      retries: 5
```

**Step 5: Docker 빌드 확인**

```bash
docker build -t panager:dev .
```

예상: 빌드 성공, 임베딩 모델 다운로드 포함

**Step 6: 커밋**

```bash
git add Dockerfile docker-compose.yml docker-compose.dev.yml docker-compose.test.yml
git commit -m "chore: Docker 설정 추가"
```

---

## Task 16: 전체 테스트 실행 및 통합 확인

**Step 1: 테스트 DB 실행**

```bash
docker compose -f docker-compose.test.yml up -d
```

**Step 2: 마이그레이션 실행**

```bash
POSTGRES_USER=panager POSTGRES_PASSWORD=panager \
POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=panager \
uv run alembic upgrade head
```

**Step 3: 전체 테스트 실행**

```bash
uv run pytest -v
```

예상: 모든 테스트 통과

**Step 4: dev 브랜치 push**

```bash
git push -u origin dev
```

**Step 5: main 브랜치 머지 (안정화 후)**

```bash
git checkout main
git merge dev
git push origin main
```
