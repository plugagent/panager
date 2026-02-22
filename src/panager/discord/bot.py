from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Dict

import discord
from langchain_core.messages import HumanMessage

from panager.discord.handlers import _stream_agent_response, handle_dm

if TYPE_CHECKING:
    from panager.services.google import GoogleService
    from panager.services.memory import MemoryService
    from panager.services.scheduler import SchedulerService

log = logging.getLogger(__name__)


class PanagerBot(discord.Client):
    """Discord 봇 인터페이스 및 세션 관리자.

    UserSessionProvider 프로토콜을 구현하여 에이전트와 Discord 간의 결합을 분리합니다.
    """

    def __init__(
        self,
        memory_service: MemoryService,
        google_service: GoogleService,
        scheduler_service: SchedulerService,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        super().__init__(intents=intents)

        self.memory_service = memory_service
        self.google_service = google_service
        self.scheduler_service = scheduler_service

        # 스케줄러 서비스에 알림 발송용 프로바이더로 자신을 등록
        self.scheduler_service.set_notification_provider(self)

        self.graph = None  # main.py에서 생성 후 주입됨
        self.auth_complete_queue: asyncio.Queue = asyncio.Queue()
        self._pending_messages: Dict[int, str] = {}

    @property
    def pending_messages(self) -> Dict[int, str]:
        """UserSessionProvider: 인증 대기 중인 메시지 맵."""
        return self._pending_messages

    async def get_user_timezone(self, user_id: int) -> str:
        """UserSessionProvider: 사용자의 타임존 조회 (기본값 서울)."""
        # FUTURE: DB 연동하여 사용자별 설정 조회
        return "Asia/Seoul"

    async def send_notification(self, user_id: int, message: str) -> None:
        """SchedulerService.NotificationProvider: 예약된 알림 발송."""
        try:
            user = await self.fetch_user(user_id)
            dm = await user.create_dm()
            await dm.send(message)
        except Exception:
            log.exception("알림 발송 실패 (user_id=%d)", user_id)

    async def setup_hook(self) -> None:
        """봇 시작 시 필요한 백그라운드 태스크 설정."""
        # 인증 완료 처리 루프 시작
        asyncio.create_task(self._process_auth_queue())
        log.info("Discord 봇 셋업 완료")

    async def _process_auth_queue(self) -> None:
        """OAuth 인증 성공 이벤트를 감시하고 보류된 요청을 재개합니다."""
        while True:
            event = await self.auth_complete_queue.get()
            user_id: int = event["user_id"]
            pending_message: str | None = self._pending_messages.pop(user_id, None)

            if not pending_message or self.graph is None:
                continue

            try:
                user = await self.fetch_user(user_id)
                dm = await user.create_dm()
                config = {"configurable": {"thread_id": str(user_id)}}
                state = {
                    "user_id": user_id,
                    "username": str(user),
                    "messages": [HumanMessage(content=pending_message)],
                }
                await _stream_agent_response(self.graph, state, config, dm)
            except Exception:
                log.exception("인증 후 재실행 실패 (user_id=%d)", user_id)

    async def on_ready(self) -> None:
        log.info("봇 로그인 완료: %s", str(self.user))

    async def on_message(self, message: discord.Message) -> None:
        """DM 메시지 수신 시 에이전트 핸들러 실행."""
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.DMChannel):
            return

        if self.graph is None:
            log.error("에이전트 그래프가 주입되지 않았습니다.")
            await message.channel.send(
                "시스템 준비 중입니다. 잠시 후 다시 시도해주세요."
            )
            return

        await handle_dm(message, self.graph)

    async def close(self) -> None:
        """봇 종료 시 리소스 정리."""
        await super().close()
