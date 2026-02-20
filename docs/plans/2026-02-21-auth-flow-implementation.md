# 인증 플로우 개선 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 봇+API를 단일 프로세스로 통합하고, Google 미연동 시 인증 안내 후 완료되면 원래 요청을 자동 재실행한다.

**Architecture:** `PanagerBot.setup_hook()`에서 uvicorn을 같은 이벤트 루프에 실행. `asyncio.Queue`로 OAuth 콜백 → 봇 브리지. `_tool_node`에서 미연동 에러를 잡아 pending 메시지 저장 + 인증 URL 반환.

**Tech Stack:** Python 3.13, discord.py, FastAPI, uvicorn, asyncio, langchain-core, asyncpg

---

## Task 1: Makefile 추가 + docker-compose.dev.yml 삭제

**Files:**
- Create: `Makefile`
- Delete: `docker-compose.dev.yml`

**Step 1: Makefile 작성**

```makefile
.PHONY: dev db db-down test migrate-test up down

# 로컬 개발: test DB 올리고 봇 핫리로드 실행
dev: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
	uv run watchfiles "python -m panager.bot.client" src

# test DB 시작 (healthy 대기)
db:
	docker compose -f docker-compose.test.yml up -d --wait

# test DB 정리
db-down:
	docker compose -f docker-compose.test.yml down

# test DB 마이그레이션
migrate-test: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
	uv run alembic upgrade head

# 테스트 (test DB 사용)
test: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
	uv run pytest -v

# 프로덕션 빌드+실행
up:
	docker compose up -d --build

# 프로덕션 정리
down:
	docker compose down
```

**Step 2: docker-compose.dev.yml 삭제**

```bash
git rm docker-compose.dev.yml
```

**Step 3: 동작 확인**

```bash
make db
make db-down
```

Expected: db_test 컨테이너가 올라갔다가 내려감.

**Step 4: Commit**

```bash
git add Makefile
git commit -m "chore: Makefile 추가 및 docker-compose.dev.yml 삭제"
```

---

## Task 2: docker-compose.yml — api 서비스 제거, panager에 포트 추가

**Files:**
- Modify: `docker-compose.yml`

**Step 1: docker-compose.yml 수정**

```yaml
services:
  migrate:
    build: .
    command: uv run alembic upgrade head
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    restart: "no"

  panager:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
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

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: api 서비스 제거, panager에 포트 8000 추가"
```

---

## Task 3: bot/client.py — uvicorn 내장 + 큐/pending 추가

**Files:**
- Modify: `src/panager/bot/client.py`

**Step 1: client.py 전체 교체**

`PanagerBot`에 다음 추가:
- `auth_complete_queue: asyncio.Queue`
- `pending_messages: dict[int, str]`
- `setup_hook()`에서 uvicorn 백그라운드 태스크 실행
- `_process_auth_queue()` 백그라운드 태스크

```python
from __future__ import annotations

import asyncio
import logging

import discord
import psycopg
import uvicorn
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
        self._pg_conn: psycopg.AsyncConnection | None = None
        self.auth_complete_queue: asyncio.Queue = asyncio.Queue()
        self.pending_messages: dict[int, str] = {}

    async def setup_hook(self) -> None:
        await init_pool(settings.postgres_dsn_asyncpg)

        self._pg_conn = await psycopg.AsyncConnection.connect(
            settings.postgres_dsn_asyncpg, autocommit=True
        )
        checkpointer = AsyncPostgresSaver(self._pg_conn)
        await checkpointer.setup()
        self.graph = build_graph(checkpointer)

        register_commands(self, self.tree)
        await self.tree.sync()

        scheduler = get_scheduler()
        scheduler.start()
        await restore_pending_schedules(self)

        # FastAPI를 같은 이벤트 루프에서 실행
        asyncio.create_task(self._run_api())
        # 인증 완료 큐 처리 백그라운드 태스크
        asyncio.create_task(self._process_auth_queue())

        log.info("봇 설정 완료")

    async def _run_api(self) -> None:
        from panager.api.main import create_app
        app = create_app(self)
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()

    async def _process_auth_queue(self) -> None:
        while True:
            event = await self.auth_complete_queue.get()
            user_id: int = event["user_id"]
            pending_message: str | None = self.pending_messages.pop(user_id, None)
            if not pending_message:
                continue
            try:
                user = await self.fetch_user(user_id)
                dm = await user.create_dm()
                from langchain_core.messages import HumanMessage
                config = {"configurable": {"thread_id": str(user_id)}}
                state = {
                    "user_id": user_id,
                    "username": str(user),
                    "messages": [HumanMessage(content=pending_message)],
                    "memory_context": "",
                }
                async with dm.typing():
                    result = await self.graph.ainvoke(state, config=config)
                    response = result["messages"][-1].content
                    await dm.send(response)
            except Exception as exc:
                log.exception("인증 후 재실행 실패: %s", exc)

    async def on_ready(self) -> None:
        log.info("봇 시작 완료: %s", str(self.user))

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
        if self._pg_conn:
            await self._pg_conn.close()
        await close_pool()
        await super().close()


async def main() -> None:
    bot = PanagerBot()
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: uvicorn을 의존성에 추가 확인**

```bash
uv add uvicorn
```

**Step 3: Commit**

```bash
git add src/panager/bot/client.py pyproject.toml uv.lock
git commit -m "feat: 봇에 uvicorn 내장 실행, auth 큐 및 pending 메시지 처리 추가"
```

---

## Task 4: api/main.py — create_app() 팩토리 패턴으로 변경

**Files:**
- Modify: `src/panager/api/main.py`

**Step 1: main.py 전체 교체**

봇 인스턴스를 인자로 받아 `app.state.bot`에 저장. DB pool은 봇이 이미 초기화했으므로 lifespan에서 제거.

```python
from __future__ import annotations

from fastapi import FastAPI

from panager.api.auth import router as auth_router


def create_app(bot) -> FastAPI:
    app = FastAPI(title="Panager API")
    app.state.bot = bot
    app.include_router(auth_router, prefix="/auth")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
```

**Step 2: Commit**

```bash
git add src/panager/api/main.py
git commit -m "refactor: FastAPI를 create_app() 팩토리로 변경, 봇 인스턴스 주입"
```

---

## Task 5: api/auth.py — 콜백에서 auth_complete_queue push

**Files:**
- Modify: `src/panager/api/auth.py`

**Step 1: auth.py 수정**

Request 객체에서 `app.state.bot`을 꺼내 큐에 push.

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from panager.google.auth import exchange_code, get_auth_url
from panager.google.repository import save_tokens

router = APIRouter()


@router.get("/google/login")
async def google_login(user_id: int):
    from fastapi.responses import RedirectResponse
    url = get_auth_url(user_id)
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(request: Request, code: str, state: str):
    try:
        user_id = int(state)
        tokens = await exchange_code(code, user_id)
        await save_tokens(user_id, tokens)

        bot = request.app.state.bot
        pending = bot.pending_messages.get(user_id)
        await bot.auth_complete_queue.put({
            "user_id": user_id,
            "message": pending,
        })

        return HTMLResponse(
            "<html><body><h2>✅ Google 연동이 완료됐습니다.</h2>"
            "<p>Discord로 돌아가세요. 잠시 후 요청하신 내용을 처리해드립니다.</p>"
            "</body></html>"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Step 2: Commit**

```bash
git add src/panager/api/auth.py
git commit -m "feat: OAuth 콜백에서 auth_complete_queue에 이벤트 push"
```

---

## Task 6: agent/graph.py — _tool_node에서 Google 미연동 에러 처리

**Files:**
- Modify: `src/panager/agent/graph.py`

**Step 1: _tool_node 수정**

`ValueError`에 "Google 계정이 연동되지 않았습니다" 포함 시 → pending 저장 + 인증 URL 반환.
봇 인스턴스는 `_tool_node`가 `state`에서 접근할 수 없으므로, `bot`을 클로저로 받는 팩토리 함수로 변경.

`build_graph()`를 `build_graph(checkpointer, bot)`으로 변경:

```python
from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from panager.agent.state import AgentState
from panager.config import Settings
from panager.google.auth import get_auth_url
from panager.google.tool import make_event_create, make_event_delete, make_event_list, make_event_update, make_task_complete, make_task_create, make_task_list
from panager.memory.tool import make_memory_save, make_memory_search
from panager.scheduler.tool import make_schedule_cancel, make_schedule_create


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


def _build_tools(user_id: int) -> list:
    return [
        make_memory_save(user_id),
        make_memory_search(user_id),
        make_schedule_create(user_id),
        make_schedule_cancel(user_id),
        make_task_create(user_id),
        make_task_list(user_id),
        make_task_complete(user_id),
        make_event_list(user_id),
        make_event_create(user_id),
        make_event_update(user_id),
        make_event_delete(user_id),
    ]


async def _agent_node(state: AgentState) -> dict:
    user_id = state["user_id"]
    tools = _build_tools(user_id)
    llm = _get_llm().bind_tools(tools)
    system_prompt = (
        f"당신은 {state['username']}의 개인 매니저 패니저입니다. "
        "사용자의 할 일, 일정, 메모리를 관리하고 적극적으로 도와주세요.\n\n"
        f"관련 메모리:\n{state.get('memory_context', '없음')}"
    )
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = await llm.ainvoke(messages)
    return {"messages": [response]}


def _make_tool_node(bot):
    async def _tool_node(state: AgentState) -> dict:
        user_id = state["user_id"]
        tools = _build_tools(user_id)
        tool_map = {t.name: t for t in tools}

        last_message = state["messages"][-1]
        tool_messages: list[ToolMessage] = []

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            if tool_name not in tool_map:
                result = f"알 수 없는 툴: {tool_name}"
            else:
                try:
                    result = await tool_map[tool_name].ainvoke(tool_args)
                except ValueError as exc:
                    if "연동되지 않았습니다" in str(exc):
                        # pending 저장
                        if bot is not None:
                            original = state["messages"][0].content
                            bot.pending_messages[user_id] = original
                        auth_url = get_auth_url(user_id)
                        result = (
                            f"Google 계정 연동이 필요합니다.\n"
                            f"아래 링크에서 연동해주세요:\n{auth_url}"
                        )
                    else:
                        result = f"오류 발생: {exc}"
                except Exception as exc:
                    result = f"오류 발생: {exc}"

            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_id)
            )

        return {"messages": tool_messages}

    return _tool_node


def _should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_graph(checkpointer, bot=None) -> object:
    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", _make_tool_node(bot))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)
```

**Step 2: client.py에서 build_graph 호출 시 bot 전달 확인**

`setup_hook()`에서:
```python
self.graph = build_graph(checkpointer, bot=self)
```

**Step 3: 기존 테스트 통과 확인**

```bash
uv run pytest tests/agent/ -v
```

Expected: PASS (bot=None으로 기존 테스트 호환)

**Step 4: Commit**

```bash
git add src/panager/agent/graph.py src/panager/bot/client.py
git commit -m "feat: Google 미연동 시 pending 저장 및 인증 URL 안내"
```

---

## Task 7: bot/handlers.py — 신규 사용자 WELCOME_MESSAGE 정리

**Files:**
- Modify: `src/panager/bot/handlers.py`

**Step 1: handlers.py 수정**

신규 사용자 첫 메시지 시 Google 연동 안내 없이 바로 에이전트 실행.
(Google 기능 요청 시 에이전트가 자동으로 안내하므로 중복 불필요)

```python
from __future__ import annotations

import logging

import discord
from discord import app_commands

from panager.db.connection import get_pool

log = logging.getLogger(__name__)


async def handle_dm(message: discord.Message, bot, graph) -> None:
    user_id = message.author.id
    pool = get_pool()

    # 신규 사용자 등록 (없으면 INSERT, 있으면 무시)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username) VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
            str(message.author),
        )

    # 에이전트 실행
    from langchain_core.messages import HumanMessage

    config = {"configurable": {"thread_id": str(user_id)}}
    state = {
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
        from panager.google.tool import make_task_list
        tool = make_task_list(interaction.user.id)
        result = await tool.ainvoke({})
        await interaction.followup.send(result)

    @tree.command(name="status", description="오늘의 요약")
    async def status_command(interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.followup.send("오늘의 요약 기능은 준비 중입니다.")
```

**Step 2: 전체 테스트 통과 확인**

```bash
uv run pytest -v
```

Expected: DB 연결 오류 2건 제외 모두 PASS

**Step 3: Commit**

```bash
git add src/panager/bot/handlers.py
git commit -m "refactor: 신규 사용자 WELCOME_MESSAGE 제거, ON CONFLICT DO NOTHING으로 단순화"
```

---

## Task 8: Docker 재배포 및 전체 동작 확인

**Step 1: 빌드 및 실행**

```bash
docker compose build panager
docker compose up -d panager
```

**Step 2: 로그 확인**

```bash
docker compose logs panager --tail=20
```

Expected: `봇 시작 완료: panager#7221`

**Step 3: API 헬스체크**

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

**Step 4: dev push**

```bash
git push origin dev
```
