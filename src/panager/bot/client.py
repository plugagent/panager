from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

import discord
import psycopg
import uvicorn
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from panager.agent.graph import build_graph
from panager.bot.handlers import handle_dm, _stream_agent_response
from panager.config import Settings
from panager.db.connection import close_pool, init_pool
from panager.logging import configure_logging
from panager.scheduler.runner import get_scheduler, restore_pending_schedules

log = logging.getLogger(__name__)
settings = Settings()
configure_logging(settings)


def _ttl_cutoff_uuid(ttl_days: int) -> str:
    """TTL 기준 시각을 UUIDv7 하한 문자열로 반환.

    LangGraph checkpoints 테이블의 checkpoint_id는 UUIDv7 형식으로,
    상위 48비트가 millisecond 타임스탬프를 인코딩합니다.
    랜덤 부분을 0으로 채운 하한 UUID를 반환하므로,
    이 값보다 작은 checkpoint_id는 TTL 초과 레코드입니다.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    ms = int(cutoff.timestamp() * 1000)
    # UUIDv7 layout: 48비트 ms | 4비트 version(0111) | 12비트 rand_a | 2비트 variant(10) | 62비트 rand_b
    # 랜덤 부분을 0으로 채워 해당 시각의 최솟값 UUID를 생성
    uuid_int = (ms << 80) | (0x7 << 76) | (0b10 << 62)
    return str(uuid.UUID(int=uuid_int))


async def _cleanup_old_checkpoints(
    conn: psycopg.AsyncConnection, ttl_days: int
) -> None:
    """TTL 초과 checkpoint 관련 행 삭제.

    LangGraph checkpoints 테이블에는 타임스탬프 컬럼이 없으므로,
    checkpoint_id (UUIDv7) 의 lexicographic 대소 비교로 TTL 기준 시각 이전 레코드를 삭제합니다.
    연관 테이블(checkpoint_writes, checkpoint_blobs)의 고아 행도 함께 정리합니다.
    """
    cutoff = _ttl_cutoff_uuid(ttl_days)

    # 1. checkpoint_writes: 삭제될 checkpoints와 같은 checkpoint_id 참조 행 먼저 삭제
    await conn.execute(
        "DELETE FROM checkpoint_writes WHERE checkpoint_id < %s",
        (cutoff,),
    )
    # 2. checkpoints: TTL 초과 행 삭제
    await conn.execute(
        "DELETE FROM checkpoints WHERE checkpoint_id < %s",
        (cutoff,),
    )
    # 3. checkpoint_blobs: 더 이상 어떤 checkpoint도 참조하지 않는 고아 행 삭제
    await conn.execute(
        """
        DELETE FROM checkpoint_blobs cb
        WHERE NOT EXISTS (
            SELECT 1 FROM checkpoints c
            WHERE c.thread_id = cb.thread_id
              AND c.checkpoint_ns = cb.checkpoint_ns
        )
        """,
    )
    log.info("오래된 checkpoint 정리 완료 (TTL: %d일)", ttl_days)


class PanagerBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        super().__init__(intents=intents)
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
        try:
            await _cleanup_old_checkpoints(self._pg_conn, settings.checkpoint_ttl_days)
        except Exception:
            log.warning("checkpoint 정리 실패 (봇은 계속 시작)", exc_info=True)
        self.graph = build_graph(checkpointer, bot=self)

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
                config = {"configurable": {"thread_id": str(user_id)}}
                state = {
                    "user_id": user_id,
                    "username": str(user),
                    "messages": [HumanMessage(content=pending_message)],
                    "memory_context": "",
                    "timezone": "Asia/Seoul",
                }
                await _stream_agent_response(self.graph, state, config, dm)
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
