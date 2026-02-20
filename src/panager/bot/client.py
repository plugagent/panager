from __future__ import annotations

import asyncio
import logging

import discord
import psycopg
import uvicorn
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from panager.agent.graph import build_graph
from panager.bot.handlers import handle_dm
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
                from langchain_core.messages import HumanMessage

                config = {"configurable": {"thread_id": str(user_id)}}
                state = {
                    "user_id": user_id,
                    "username": str(user),
                    "messages": [HumanMessage(content=pending_message)],
                    "memory_context": "",
                    "timezone": "Asia/Seoul",
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
