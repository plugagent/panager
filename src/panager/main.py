from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row
import uvicorn
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from panager.agent.workflow import build_graph
from panager.api.main import create_app
from panager.core.config import Settings
from panager.core.logging import configure_logging
from panager.db.connection import close_pool, init_pool
from panager.discord.bot import PanagerBot
from panager.services.google import GoogleService
from panager.services.github import GithubService
from panager.services.notion import NotionService
from panager.services.memory import MemoryService
from panager.services.scheduler import SchedulerService

log = logging.getLogger(__name__)


def _ttl_cutoff_uuid(ttl_days: int) -> str:
    """TTL 기준 시각을 UUIDv7 하한 문자열로 반환.

    LangGraph의 AsyncPostgresSaver는 체크포인트 ID로 UUIDv7을 사용하므로,
    비트 조작을 통해 특정 시점 이전의 UUID 하한선을 생성하여 효율적으로 삭제합니다.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    ms = int(cutoff.timestamp() * 1000)
    # UUIDv7 layout: 48비트 ms | 4비트 version(0111) | 12비트 rand_a | 2비트 variant(10) | 62비트 rand_b
    uuid_int = (ms << 80) | (0x7 << 76) | (0b10 << 62)
    return str(uuid.UUID(int=uuid_int))


async def _cleanup_old_checkpoints(
    conn: psycopg.AsyncConnection, ttl_days: int
) -> None:
    """오래된 LangGraph checkpoint를 정리합니다."""
    cutoff = _ttl_cutoff_uuid(ttl_days)

    await conn.execute(
        "DELETE FROM checkpoint_writes WHERE checkpoint_id < %s",
        (cutoff,),
    )
    await conn.execute(
        "DELETE FROM checkpoints WHERE checkpoint_id < %s",
        (cutoff,),
    )
    await conn.execute(
        """
        DELETE FROM checkpoint_blobs cb
        WHERE NOT EXISTS (
            SELECT 1 FROM checkpoints c
            WHERE c.thread_id = cb.thread_id
              AND c.checkpoint_ns = cb.checkpoint_ns
        )
        """,
    )
    log.info("오래된 checkpoint 정리 완료 (TTL: %d일)", ttl_days)


async def main() -> None:
    """애플리케이션 진입점 및 오케스트레이션."""
    try:
        settings = Settings()
    except Exception as e:
        print(f"설정 로드 실패: {e}")
        return

    # 로그 디렉토리 생성
    log_dir = os.path.dirname(settings.log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    configure_logging(settings)

    log.info("애플리케이션 시작 중...")

    # 1. DB pool 초기화 (asyncpg용)
    pool = await init_pool(settings.postgres_dsn_asyncpg)

    # 2. psycopg 연결 및 Checkpointer 설정 (LangGraph용)
    pg_conn = await psycopg.AsyncConnection.connect(
        settings.postgres_dsn_asyncpg, autocommit=True, row_factory=dict_row
    )
    checkpointer = AsyncPostgresSaver(pg_conn)
    await checkpointer.setup()

    # 3. 오래된 checkpoint 정리
    try:
        await _cleanup_old_checkpoints(pg_conn, settings.checkpoint_ttl_days)
    except Exception:
        log.warning("checkpoint 정리 실패 (애플리케이션은 계속 시작)", exc_info=True)

    # 4. 서비스 레이어 초기화
    memory_service = MemoryService(pool)
    google_service = GoogleService(settings, pool)
    github_service = GithubService(settings, pool)
    notion_service = NotionService(settings, pool)
    scheduler_service = SchedulerService(pool)

    # 4.5 도구 레지스트리 초기화 및 인덱싱
    from panager.agent.registry import ToolRegistry

    registry = ToolRegistry(pool, settings)

    # 프로토타입 생성 (인덱싱용, user_id=0은 실제 사용되지 않음)
    # 실제 도구 로직은 await 서비스 호출 시 에러가 날 수 있으나, 인덱싱은 name/description만 필요
    from panager.tools.google import (
        make_manage_google_calendar,
        make_manage_google_tasks,
    )
    from panager.tools.github import make_github_tools
    from panager.tools.notion import make_notion_tools
    from panager.tools.memory import make_memory_tools
    from panager.tools.scheduler import make_scheduler_tools

    prototypes = [
        make_manage_google_calendar(0, google_service),
        make_manage_google_tasks(0, google_service),
    ]

    prototypes.extend(make_github_tools(0, github_service))
    prototypes.extend(make_notion_tools(0, notion_service))
    prototypes.extend(make_memory_tools())
    prototypes.extend(make_scheduler_tools())

    # 메모리 레지스트리에 프로토타입 등록 (메모리상에서는 필터링용으로 사용)
    # 실제 워타임에는 user_id에 맞게 재생성됨
    registry.register_tools(prototypes)

    # DB와 동기화 (임베딩 생성 및 저장)
    await registry.sync_to_db()

    # 5. Discord 봇 초기화 (UserSessionProvider 구현체)
    bot = PanagerBot(
        memory_service=memory_service,
        google_service=google_service,
        github_service=github_service,
        notion_service=notion_service,
        scheduler_service=scheduler_service,
        registry=registry,
    )

    # 6. 에이전트 워크플로우(LangGraph) 빌드 및 주입
    graph = build_graph(
        checkpointer=checkpointer,
        session_provider=bot,
        memory_service=memory_service,
        google_service=google_service,
        github_service=github_service,
        notion_service=notion_service,
        scheduler_service=scheduler_service,
        registry=registry,
    )
    bot.graph = graph

    # 7. FastAPI API 서버 시작 (백그라운드)
    app = create_app(bot)
    api_config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
    api_server = uvicorn.Server(api_config)
    api_task = asyncio.create_task(api_server.serve())

    # 8. 미발송 스케줄 복구
    await scheduler_service.restore_schedules()

    # 9. 봇 시작
    try:
        async with bot:
            await bot.start(settings.discord_token)
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("애플리케이션 종료 신호 수신")
    finally:
        log.info("리소스 정리 중...")
        # API 서버 종료
        api_task.cancel()
        try:
            await api_task
        except asyncio.CancelledError:
            pass

        # DB 연결 종료
        await pg_conn.close()
        await close_pool()
        log.info("정리 완료. 애플리케이션을 종료합니다.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
