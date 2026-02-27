from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Dict, Any

import discord
from langchain_core.messages import HumanMessage

from panager.agent.state import PendingReflection
from panager.discord.handlers import _stream_agent_response, handle_dm

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph as CompiledGraph
    from panager.agent.registry import ToolRegistry
    from panager.services.google import GoogleService
    from panager.services.github import GithubService
    from panager.services.notion import NotionService
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
        github_service: GithubService,
        notion_service: NotionService,
        scheduler_service: SchedulerService,
        registry: ToolRegistry,
    ) -> None:
        super().__init__(intents=discord.Intents.default())
        self.memory_service = memory_service
        self.google_service = google_service
        self.github_service = github_service
        self.notion_service = notion_service
        self.scheduler_service = scheduler_service
        self.registry = registry

        # 스케줄러 서비스에 알림 발송용 프로바이더로 자신을 등록
        self.scheduler_service.set_notification_provider(self)

        self.graph: CompiledGraph | None = None  # main.py에서 생성 후 주입됨
        self.auth_complete_queue: asyncio.Queue = asyncio.Queue()
        self._pending_messages: Dict[int, str] = {}
        self._user_locks: Dict[int, asyncio.Lock] = {}

    @property
    def pending_messages(self) -> Dict[int, str]:
        """UserSessionProvider: 인증 대기 중인 메시지 맵."""
        return self._pending_messages

    def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        """사용자별 락을 가져오거나 생성합니다."""
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    async def get_user_timezone(self, user_id: int) -> str:
        """UserSessionProvider: 사용자의 타임존 조회 (기본값 서울)."""
        # FUTURE: DB 연동하여 사용자별 설정 조회
        return "Asia/Seoul"

    async def send_notification(self, user_id: int, message: str) -> None:
        """SchedulerService.NotificationProvider: 예약된 알림 발송."""
        async with self._get_user_lock(user_id):
            try:
                user = await self.fetch_user(user_id)
                dm = await user.create_dm()
                await dm.send(message)
            except Exception:
                log.exception("알림 발송 실패 (user_id=%d)", user_id)

    async def trigger_task(
        self, user_id: int, command: str, payload: Dict[str, Any] | None = None
    ) -> None:
        """SchedulerService.NotificationProvider: 에이전트 작업 트리거."""
        if self.graph is None:
            log.error("에이전트 그래프가 주입되지 않았습니다.")
            return

        async with self._get_user_lock(user_id):
            try:
                user = await self.fetch_user(user_id)
                dm = await user.create_dm()
                config = {"configurable": {"thread_id": str(user_id)}}
                state: dict[str, Any] = {
                    "user_id": user_id,
                    "username": str(user),
                    "messages": [HumanMessage(content=command)],
                    "is_system_trigger": True,
                }
                if payload and "pending_reflections" in payload:
                    # dict 리스트를 Pydantic 모델 리스트로 변환하여 타입 안전성 확보
                    state["pending_reflections"] = [
                        PendingReflection(**r) if isinstance(r, dict) else r
                        for r in payload["pending_reflections"]
                    ]

                log.info(
                    "예약된 태스크 트리거 (user_id=%d, command=%s)", user_id, command
                )
                await _stream_agent_response(self.graph, state, config, dm)
            except Exception:
                log.exception("태스크 트리거 실패 (user_id=%d)", user_id)

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

            # 인증 완료 후 재개를 위해 보류된 요청이 있는지 확인
            if user_id not in self._pending_messages or self.graph is None:
                continue

            try:
                user = await self.fetch_user(user_id)
                dm = await user.create_dm()
                config = {"configurable": {"thread_id": str(user_id)}}

                # 인증 메시지 재사용 (단일 메시지 UX)
                current_state = await self.graph.aget_state(config)
                auth_message_id = current_state.values.get("auth_message_id")

                initial_msg = None
                if auth_message_id:
                    try:
                        initial_msg = await dm.fetch_message(auth_message_id)
                    except Exception:
                        log.debug("이전 인증 메시지를 찾을 수 없음 (새로 생성)")

                # Resume 모드로 실행 (state=None)
                # 이 시점에서 graph는 인터럽트 지점(툴 실행 후)에서 대기 중임
                async with self._get_user_lock(user_id):
                    await _stream_agent_response(
                        self.graph, None, config, dm, initial_msg=initial_msg
                    )

                # 작업 완료 후 보류 메시지 제거
                self._pending_messages.pop(user_id, None)

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

        user_id = message.author.id
        # 요청 시작 시 보류 메시지에 등록
        self._pending_messages[user_id] = message.content

        async with self._get_user_lock(user_id):
            await handle_dm(message, self.graph)

            # 작업이 정상 종료(인증 인터럽트 없이)된 경우 보류 메시지 제거
            # 인증 인터럽트가 발생했다면 _process_auth_queue에서 제거됨
            config = {"configurable": {"thread_id": str(user_id)}}
            try:
                state_snapshot = await self.graph.aget_state(config)
                if not state_snapshot.values.get("auth_request_url"):
                    self._pending_messages.pop(user_id, None)
            except Exception:
                pass

    async def close(self) -> None:
        """봇 종료 시 리소스 정리."""
        await super().close()
