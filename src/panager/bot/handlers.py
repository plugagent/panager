from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import discord
from langchain_core.messages import AIMessageChunk, HumanMessage

from panager.bot.views import ConfirmView, HITL_TOOL_LABELS
from panager.db.connection import get_pool

log = logging.getLogger(__name__)

STREAM_DEBOUNCE = 0.2  # seconds — Discord rate limit 대응


async def _stream_agent_response(
    graph: Any,
    state: Any,  # dict (새 실행) 또는 Command (resume)
    config: dict,
    channel: discord.abc.Messageable,
) -> None:
    """
    LangGraph graph를 스트리밍 모드로 실행하고,
    Discord 채널에 점진적으로 메시지를 전송/수정한다.

    - channel.send()와 graph.astream()을 동시에 시작해 Discord API
      왕복 latency를 LLM 준비 시간과 겹친다.
    - 첫 AI 청크 수신 시 send_task를 await해 sent_message를 확보한다.
    - 200ms 디바운스로 edit() 호출 (rate limit 대응)
    - 스트림 종료 후 커서 제거한 최종 텍스트로 edit()
    """
    # channel.send와 graph.astream을 동시에 시작
    send_task: asyncio.Task[discord.Message] = asyncio.create_task(
        channel.send("생각하는 중...")
    )
    sent_message: discord.Message | None = None
    accumulated = ""
    # 0.0 ensures the first chunk always triggers an edit
    last_edit_at = 0.0

    try:
        async for chunk, _metadata in graph.astream(
            state, config=config, stream_mode="messages"
        ):
            if not isinstance(chunk, AIMessageChunk):
                continue
            if not chunk.content:
                continue
            if not isinstance(chunk.content, str):
                continue

            # 첫 청크 도착 시 send_task 완료 대기 (이미 완료돼 있을 가능성 높음)
            if sent_message is None:
                sent_message = await send_task

            accumulated += chunk.content

            # 디바운스: 마지막 edit 이후 DEBOUNCE 초 이상 경과 시에만 edit
            now = time.monotonic()
            if now - last_edit_at >= STREAM_DEBOUNCE:
                await sent_message.edit(content=accumulated + "▌")
                last_edit_at = now

    finally:
        # 빈 스트림이거나 send가 아직 완료 안 된 경우, 예외 발생 시에도 보장
        if sent_message is None:
            sent_message = await send_task

        # 최종 edit: 커서 제거
        final_text = accumulated.strip() or "(응답을 받지 못했습니다.)"
        await sent_message.edit(content=final_text)


async def handle_dm(message: discord.Message, bot: Any, graph: Any) -> None:
    user_id = message.author.id
    pool = get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username) VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
            str(message.author),
        )

    config = {"configurable": {"thread_id": str(user_id)}}

    # interrupt 대기 중인지 확인
    snapshot = await graph.aget_state(config)
    if snapshot.next:
        await message.channel.send(
            "이전 작업 확인을 기다리고 있어요. 위의 버튼을 눌러주세요."
        )
        return

    state = {
        "user_id": user_id,
        "username": str(message.author),
        "messages": [HumanMessage(content=message.content)],
        "memory_context": "",
        "timezone": "Asia/Seoul",
    }

    await _stream_agent_response(graph, state, config, message.channel)

    # 실행 후 interrupt 발생 여부 확인 (HITL 툴 호출 시)
    snapshot_after = await graph.aget_state(config)
    if snapshot_after.next:
        try:
            tool_call = snapshot_after.tasks[0].interrupts[0].value["tool_call"]
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            label = HITL_TOOL_LABELS.get(tool_name, tool_name)
            args_text = "\n".join(f"  {k}: {v}" for k, v in tool_args.items())
            confirm_text = (
                f"패니저가 다음 작업을 실행하려 합니다:\n\n"
                f"**{label}**\n{args_text}\n\n"
                "진행하시겠습니까?"
            )
            view = ConfirmView(thread_id=str(user_id), bot=bot)
            await message.channel.send(confirm_text, view=view)
        except Exception as exc:
            log.warning("HITL 확인 메시지 전송 실패: %s", exc)
