from __future__ import annotations

from typing import Any

import discord

HITL_TOOL_LABELS: dict[str, str] = {
    "schedule_create": "일정 예약",
    "recurring_event_create": "반복 이벤트 생성",
    "task_delete": "할 일 삭제",
}


class ConfirmView(discord.ui.View):
    """HITL 확인 버튼 UI — 5분 타임아웃."""

    def __init__(self, thread_id: str, bot: Any) -> None:
        super().__init__(timeout=300)
        self.thread_id = thread_id
        self.bot = bot

    @discord.ui.button(label="✅ 예", style=discord.ButtonStyle.success)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        self.bot.hitl_queue.put_nowait(
            {"thread_id": self.thread_id, "resume": "approved"}
        )
        self.stop()

    @discord.ui.button(label="❌ 아니오", style=discord.ButtonStyle.danger)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        self.bot.hitl_queue.put_nowait(
            {"thread_id": self.thread_id, "resume": "rejected"}
        )
        self.stop()

    async def on_timeout(self) -> None:
        """5분 타임아웃 시 자동으로 거절 처리."""
        self.bot.hitl_queue.put_nowait(
            {"thread_id": self.thread_id, "resume": "rejected"}
        )
