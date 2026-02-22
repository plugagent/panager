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
    sent_messages: list[discord.Message] = [await channel.send("생각하는 중...")]
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
            # 현재 메시지 인덱스와 해당 메시지에 들어갈 내용 계산
            current_msg_index = len(accumulated) // MAX_MESSAGE_LENGTH
            current_msg_content = accumulated[current_msg_index * MAX_MESSAGE_LENGTH :]

            # 필요한 경우 새 메시지 생성
            while len(sent_messages) <= current_msg_index:
                new_msg = await channel.send("...")
                sent_messages.append(new_msg)

            # 현재 메시지 업데이트 (커서 포함)
            await sent_messages[current_msg_index].edit(
                content=current_msg_content + "▌"
            )
            last_edit_at = now

    # 최종 응답 업데이트 및 정리
    full_text = accumulated.strip() or "(응답을 받지 못했습니다.)"
    chunks = [
        full_text[i : i + MAX_MESSAGE_LENGTH]
        for i in range(0, len(full_text), MAX_MESSAGE_LENGTH)
    ]

    for i, content in enumerate(chunks):
        if i < len(sent_messages):
            await sent_messages[i].edit(content=content)
        else:
            await channel.send(content)

    # 혹시 남은 대기 메시지가 있다면 삭제 (생각하는 중... 등이 남았을 경우)
    if len(sent_messages) > len(chunks):
        for msg in sent_messages[len(chunks) :]:
            try:
                await msg.delete()
            except Exception:
                pass


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
