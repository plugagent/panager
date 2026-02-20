from __future__ import annotations

import asyncio
import logging

import discord
import psycopg
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
        log.info("봇 설정 완료")

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
