from __future__ import annotations

import logging
import time

import discord
from langchain_core.messages import AIMessageChunk, HumanMessage

from panager.db.connection import get_pool

log = logging.getLogger(__name__)

STREAM_DEBOUNCE = 0.2  # seconds — Discord rate limit 대응


async def _stream_agent_response(graph, state: dict, config: dict, channel) -> None:
    """
    LangGraph graph를 스트리밍 모드로 실행하고,
    Discord 채널에 점진적으로 메시지를 전송/수정한다.

    - 첫 토큰 수신 시 '▌' 초기 메시지 전송
    - 200ms 디바운스로 edit() 호출 (rate limit 대응)
    - 스트림 종료 후 커서 제거한 최종 텍스트로 edit()
    """
    accumulated = ""
    sent_message = None
    last_edit_at = 0.0

    async for chunk, _metadata in graph.astream(
        state, config=config, stream_mode="messages"
    ):
        if not isinstance(chunk, AIMessageChunk):
            continue
        if not chunk.content:
            continue
        if not isinstance(chunk.content, str):
            continue

        accumulated += chunk.content

        # 첫 토큰: 초기 메시지 전송 후 타이머 시작 (전송 직후부터 디바운스 측정)
        if sent_message is None:
            sent_message = await channel.send("▌")
            last_edit_at = time.monotonic()

        # 디바운스: 마지막 edit 이후 DEBOUNCE 초 이상 경과 시에만 edit
        now = time.monotonic()
        if now - last_edit_at >= STREAM_DEBOUNCE:
            await sent_message.edit(content=accumulated + "▌")
            last_edit_at = now

    # 최종 edit: 커서 제거
    final_text = accumulated.strip() or "(응답을 받지 못했습니다.)"
    if sent_message is None:
        # 스트림이 완전히 비어있는 경우
        await channel.send(final_text)
    else:
        await sent_message.edit(content=final_text)


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
    config = {"configurable": {"thread_id": str(user_id)}}
    state = {
        "user_id": user_id,
        "username": str(message.author),
        "messages": [HumanMessage(content=message.content)],
        "memory_context": "",
        "timezone": "Asia/Seoul",
    }

    await _stream_agent_response(graph, state, config, message.channel)
