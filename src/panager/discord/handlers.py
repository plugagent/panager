from __future__ import annotations

import logging
import time
from typing import Any, Dict

import discord
from langchain_core.messages import AIMessageChunk, HumanMessage

from panager.db.connection import get_pool

# Discord 메시지 길이 제한 (2,000자)
MAX_MESSAGE_LENGTH = 2000
STREAM_DEBOUNCE = 0.3

log = logging.getLogger(__name__)


class ResponseManager:
    """Discord 단일 메시지의 상태와 내용을 관리하는 도우미 클래스."""

    def __init__(
        self,
        channel: discord.abc.Messageable,
        initial_msg: discord.Message | None = None,
    ):
        self.channel = channel
        self.main_msg = initial_msg
        self.accumulated_text = ""
        self.current_status = "생각하는 중..."
        self.last_edit_at = 0.0
        self._finalized = False

    async def update_status(self, node_name: str, tool_name: str | None = None):
        """실행 단계에 따른 상태 문구를 업데이트합니다."""
        status_map = {
            "discovery": "의도를 파악하고 있습니다...",
            "supervisor": "관련 도구를 검색하고 계획을 세우는 중입니다...",
            "tool_executor": "도구 실행 중",
            "auth_interrupt": "보안 인증이 필요합니다.",
        }

        new_status = status_map.get(node_name, "작업 중...")
        if node_name == "tool_executor" and tool_name:
            new_status = f"도구 실행 중: `{tool_name}`..."

        if self.current_status != new_status:
            self.current_status = new_status
            await self._render(force=True)

    async def append_text(self, text: str):
        """AI 응답 텍스트를 누적하고 주기적으로 메시지를 수정합니다."""
        self.accumulated_text += text
        await self._render()

    async def _render(self, force: bool = False):
        """현재 상태와 텍스트를 결합하여 Discord 메시지를 업데이트합니다."""
        if self._finalized:
            return

        now = time.monotonic()
        if not force and (now - self.last_edit_at < STREAM_DEBOUNCE):
            return

        # 메시지 구성
        content = self.accumulated_text
        if not self._finalized:
            # 작업 중일 때는 상태 표시와 커서 추가
            status_line = (
                f"\n\n*( {self.current_status} )*" if self.current_status else ""
            )
            content = (content + "▌" + status_line).strip()

        if not content:
            content = "..."

        # 길이 제한
        content = content[:MAX_MESSAGE_LENGTH]

        try:
            if self.main_msg:
                await self.main_msg.edit(content=content)
            else:
                self.main_msg = await self.channel.send(content)
            self.last_edit_at = now
        except discord.HTTPException as e:
            log.warning("메시지 편집 실패: %s", e)

    async def finalize(self, auth_url: str | None = None):
        """상태 표시를 제거하고 최종 메시지를 확정합니다."""
        self._finalized = True

        text = self.accumulated_text.strip()
        if auth_url:
            provider = "Google"
            if "github" in auth_url:
                provider = "GitHub"
            elif "notion" in auth_url:
                provider = "Notion"

            auth_info = f"\n\n**{provider} 인증이 필요합니다.**\n[여기 클릭하여 인증 완료]({auth_url})"
            text += auth_info

        if not text:
            text = "(응답을 받지 못했습니다.)"

        final_content = text[:MAX_MESSAGE_LENGTH]
        try:
            if self.main_msg:
                await self.main_msg.edit(content=final_content)
            else:
                await self.channel.send(final_content)
        except discord.HTTPException:
            log.exception("최종 메시지 확정 실패")


async def _stream_agent_response(
    graph: Any,
    state: Dict[str, Any],
    config: Dict[str, Any],
    channel: discord.abc.Messageable,
    initial_msg: discord.Message | None = None,
) -> None:
    """에이전트 실행 과정을 추적하며 단일 메시지로 스트리밍합니다."""
    ui = ResponseManager(channel, initial_msg)

    try:
        # updates 모드를 사용하여 노드 전환 감지, messages 모드를 사용하여 텍스트 스트리밍
        async for event_type, chunk in graph.astream(
            state, config=config, stream_mode=["updates", "messages"]
        ):
            if event_type == "updates":
                # 노드 완료 시 다음 단계 예측 또는 현재 완료된 노드 기반 상태 업데이트
                node_name = next(iter(chunk))
                node_output = chunk[node_name]

                # 다음 노드를 위한 정보 추출
                tool_name = None
                if node_name == "supervisor":
                    # supervisor가 도구를 호출하기로 했다면 마지막 메시지에서 이름 추출
                    if "messages" in node_output and node_output["messages"]:
                        last_ai_msg = node_output["messages"][-1]
                        if (
                            hasattr(last_ai_msg, "tool_calls")
                            and last_ai_msg.tool_calls
                        ):
                            tool_name = last_ai_msg.tool_calls[0]["name"]

                await ui.update_status(node_name, tool_name=tool_name)

            elif event_type == "messages":
                # AI 메시지 스트리밍
                msg_chunk, metadata = chunk
                if isinstance(msg_chunk, AIMessageChunk) and isinstance(
                    msg_chunk.content, str
                ):
                    if msg_chunk.content:
                        # 텍스트가 오는 시점은 보통 supervisor 노드
                        await ui.update_status(
                            metadata.get("langgraph_node", "supervisor")
                        )
                        await ui.append_text(msg_chunk.content)

    except Exception as e:
        log.error("에이전트 실행 중 오류 발생: %s", e, exc_info=True)
        await ui.append_text(f"\n\n⚠️ **오류 발생:** {str(e)}")

    # 최종 상태 확인 및 마무리
    auth_url = None
    try:
        state_snapshot = await graph.aget_state(config)
        auth_url = state_snapshot.values.get("auth_request_url")
    except Exception:
        pass

    await ui.finalize(auth_url=auth_url)


async def handle_dm(message: discord.Message, graph: Any) -> None:
    """사용자 DM을 처리하고 에이전트 그래프를 실행합니다."""
    user_id = message.author.id
    pool = get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
            user_id,
            str(message.author),
        )

    config = {"configurable": {"thread_id": str(user_id)}}
    input_state = {
        "user_id": user_id,
        "username": str(message.author),
        "messages": [HumanMessage(content=message.content)],
        "is_system_trigger": False,
    }

    await _stream_agent_response(graph, input_state, config, message.channel)
