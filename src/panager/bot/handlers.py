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
