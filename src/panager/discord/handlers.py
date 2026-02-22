from __future__ import annotations

import time
from typing import Any, Dict

import discord
from langchain_core.messages import AIMessageChunk, HumanMessage

from panager.db.connection import get_pool

# Discord 메시지 길이 제한 (2,000자)
MAX_MESSAGE_LENGTH = 2000
STREAM_DEBOUNCE = 0.2


async def _stream_agent_response(
    graph: Any,
    state: Dict[str, Any],
    config: Dict[str, Any],
    channel: discord.abc.Messageable,
) -> None:
    """에이전트 응답을 스트리밍하여 Discord에 전송합니다."""
    # LLM 응답 전에 대기 문구 전송
    sent_message = await channel.send("생각하는 중...")
    accumulated = ""
    last_edit_at = 0.0

    async for chunk, _metadata in graph.astream(
        state, config=config, stream_mode="messages"
    ):
        if not isinstance(chunk, AIMessageChunk) or not isinstance(chunk.content, str):
            continue

        if not chunk.content:
            continue

        accumulated += chunk.content

        # 디바운스: 스트리밍 중 주기적으로 메시지 업데이트
        now = time.monotonic()
        if now - last_edit_at >= STREAM_DEBOUNCE:
            display_text = accumulated
            # 2,000자 제한 확인 (커서와 안내 문구 포함 여유분)
            if len(display_text) > MAX_MESSAGE_LENGTH - 100:
                display_text = display_text[: MAX_MESSAGE_LENGTH - 100] + "... (생략)"

            await sent_message.edit(content=display_text + "▌")
            last_edit_at = now

    # 최종 응답 업데이트
    final_text = accumulated.strip() or "(응답을 받지 못했습니다.)"
    if len(final_text) > MAX_MESSAGE_LENGTH:
        final_text = (
            final_text[: MAX_MESSAGE_LENGTH - 50]
            + "... (내용이 너무 길어 생략되었습니다.)"
        )

    await sent_message.edit(content=final_text)


async def handle_dm(message: discord.Message, graph: Any) -> None:
    """사용자 DM을 처리하고 에이전트 그래프를 실행합니다."""
    user_id = message.author.id
    pool = get_pool()

    # 신규 사용자 등록 (DB 연동)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username) VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
            str(message.author),
        )

    # 에이전트 실행 설정
    config = {"configurable": {"thread_id": str(user_id)}}
    state = {
        "user_id": user_id,
        "username": str(message.author),
        "messages": [HumanMessage(content=message.content)],
    }

    await _stream_agent_response(graph, state, config, message.channel)
