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
    # ... (thinking message etc)
    # ...
    # (rest of code before loop)
    sent_messages: list[discord.Message] = [await channel.send("생각하는 중...")]
    accumulated = ""
    last_edit_at = 0.0

    async for chunk, _metadata in graph.astream(
        state, config=config, stream_mode="messages"
    ):
        # supervisor 노드의 출력(JSON 라우팅 정보 등)은 건너뜀
        if _metadata.get("langgraph_node") == "supervisor":
            continue

        if not isinstance(chunk, AIMessageChunk) or not isinstance(chunk.content, str):
            continue

        if not chunk.content:
            continue

        accumulated += chunk.content
        # ... (debounce logic)
        now = time.monotonic()
        if now - last_edit_at >= STREAM_DEBOUNCE:
            current_msg_index = len(accumulated) // MAX_MESSAGE_LENGTH
            current_msg_content = accumulated[current_msg_index * MAX_MESSAGE_LENGTH :]
            while len(sent_messages) <= current_msg_index:
                new_msg = await channel.send("...")
                sent_messages.append(new_msg)
            await sent_messages[current_msg_index].edit(
                content=current_msg_content + "▌"
            )
            last_edit_at = now

    # 최종 응답 업데이트
    full_text = accumulated.strip() or "(응답을 받지 못했습니다.)"
    # ... (chunks and edit logic)
    chunks = [
        full_text[i : i + MAX_MESSAGE_LENGTH]
        for i in range(0, len(full_text), MAX_MESSAGE_LENGTH)
    ]

    for i, content in enumerate(chunks):
        if i < len(sent_messages):
            await sent_messages[i].edit(content=content)
        else:
            await channel.send(content)

    if len(sent_messages) > len(chunks):
        for msg in sent_messages[len(chunks) :]:
            try:
                await msg.delete()
            except Exception:
                pass

    # --- 인터럽트(인증) 처리 추가 ---
    current_state = await graph.get_state(config)
    if current_state.next:
        # 인터럽트 상태인지 확인
        for task in current_state.tasks:
            if task.interrupts:
                # 첫 번째 인터럽트 정보 추출
                info = task.interrupts[0]
                if isinstance(info, dict):
                    int_type = info.get("type")
                    auth_url = info.get("url")

                    if (
                        int_type
                        and auth_url
                        and int_type
                        in [
                            "google_auth_required",
                            "github_auth_required",
                            "notion_auth_required",
                        ]
                    ):
                        provider = str(int_type).split("_")[0].capitalize()

                        auth_msg = await channel.send(
                            f"🔑 **{provider} 인증이 필요합니다.**\n"
                            f"아래 링크를 통해 인증을 완료해주세요:\n{auth_url}"
                        )

                    # 인증 메시지 ID를 상태에 저장하여 나중에 정리할 수 있게 함
                    await graph.update_state(
                        config,
                        {"auth_message_id": auth_msg.id},
                    )
                break


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
        "is_system_trigger": False,
    }

    await _stream_agent_response(graph, state, config, message.channel)
