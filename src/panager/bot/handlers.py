from __future__ import annotations

import logging

import discord
from discord import app_commands

from panager.db.connection import get_pool

log = logging.getLogger(__name__)

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
            await message.channel.send(WELCOME_MESSAGE.format(auth_url=auth_url))
            return

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
        from panager.google.tool import task_list

        result = await task_list.ainvoke({"user_id": interaction.user.id})
        await interaction.followup.send(result)

    @tree.command(name="status", description="오늘의 요약")
    async def status_command(interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.followup.send("오늘의 요약 기능은 준비 중입니다.")
