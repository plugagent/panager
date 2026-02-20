from __future__ import annotations

import logging

import discord

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
        "timezone": "Asia/Seoul",
    }

    async with message.channel.typing():
        result = await graph.ainvoke(state, config=config)
        response = result["messages"][-1].content
        await message.channel.send(response)
