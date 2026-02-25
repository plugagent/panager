from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from panager.agent.google.graph import build_google_worker
from panager.agent.memory.graph import build_memory_worker
from panager.agent.scheduler.graph import build_scheduler_worker
from panager.agent.state import AgentState, WorkerState
from panager.agent.supervisor import supervisor_node
from panager.agent.utils import get_llm
from panager.core.config import Settings

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph import CompiledGraph
    from panager.agent.interfaces import UserSessionProvider
    from panager.services.google import GoogleService
    from panager.services.memory import MemoryService
    from panager.services.scheduler import SchedulerService


log = logging.getLogger(__name__)


def _build_tools(
    user_id: int,
    memory_service: MemoryService,
    google_service: GoogleService,
    scheduler_service: SchedulerService,
) -> list:
    """user_id를 클로저로 포함한 tool 인스턴스 목록을 반환합니다."""
    from panager.agent.google.tools import (
        make_manage_google_calendar,
        make_manage_google_tasks,
    )
    from panager.agent.memory.tools import make_manage_user_memory
    from panager.agent.scheduler.tools import make_manage_dm_scheduler

    return [
        make_manage_user_memory(user_id, memory_service),
        make_manage_dm_scheduler(user_id, scheduler_service),
        make_manage_google_tasks(user_id, google_service),
        make_manage_google_calendar(user_id, google_service),
    ]


def auth_interrupt_node(state: AgentState):
    """Google 인증이 필요한 경우 실행을 일시 중단하고 사용자 승인을 기다립니다."""
    auth_url = state.get("auth_request_url")
    if auth_url:
        resume_data = interrupt({"type": "google_auth_required", "url": auth_url})

        # resume_data가 "auth_success" 문자열이거나 {"status": "auth_success"} 형태인 경우 처리
        is_success = False
        if resume_data == "auth_success":
            is_success = True
        elif (
            isinstance(resume_data, dict)
            and resume_data.get("status") == "auth_success"
        ):
            is_success = True

        if is_success:
            return {
                "auth_request_url": None,
                "next_worker": "GoogleWorker",
            }  # Retry GoogleWorker

        # 인증 취소 또는 다른 데이터가 들어온 경우 종료로 유도
        return {
            "auth_request_url": None,
            "next_worker": "FINISH",
        }
    return {}


def build_graph(
    checkpointer: BaseCheckpointSaver,
    session_provider: UserSessionProvider,
    memory_service: MemoryService,
    google_service: GoogleService,
    scheduler_service: SchedulerService,
) -> CompiledGraph:
    settings = Settings()
    llm = get_llm(settings)

    # 1. 서브 워커 빌드
    google_worker = build_google_worker(
        llm, google_service, memory_service, scheduler_service
    )
    memory_worker = build_memory_worker(llm)
    scheduler_worker = build_scheduler_worker(llm)

    # 2. 메인 그래프 구성
    graph = StateGraph(AgentState)

    # 노드 추가
    graph.add_node(
        "supervisor",
        functools.partial(
            supervisor_node, settings=settings, session_provider=session_provider
        ),
    )
    graph.add_node("auth_interrupt", auth_interrupt_node)

    # 워커 노드 래퍼 정의
    async def call_google_worker(state: AgentState) -> dict:
        worker_state: WorkerState = {
            "messages": state["messages"],
            "task": "Manage Google Calendar and Tasks",
            "main_context": dict(state),
        }
        res = await google_worker.ainvoke(worker_state)
        return {
            "messages": res["messages"],
            "task_summary": res.get("task_summary", ""),
            "auth_request_url": res.get("auth_request_url"),
        }

    async def call_memory_worker(state: AgentState) -> dict:
        worker_state: WorkerState = {
            "messages": state["messages"],
            "task": "Manage user memory",
            "main_context": dict(state),
        }
        res = await memory_worker.ainvoke(worker_state)
        return {
            "messages": res["messages"],
            "task_summary": res.get("task_summary", ""),
        }

    async def call_scheduler_worker(state: AgentState) -> dict:
        worker_state: WorkerState = {
            "messages": state["messages"],
            "task": "Manage dm scheduler",
            "main_context": dict(state),
        }
        res = await scheduler_worker.ainvoke(worker_state)
        return {
            "messages": res["messages"],
            "task_summary": res.get("task_summary", ""),
        }

    graph.add_node("GoogleWorker", call_google_worker)
    graph.add_node("MemoryWorker", call_memory_worker)
    graph.add_node("SchedulerWorker", call_scheduler_worker)

    # 엣지 연결
    graph.add_edge(START, "supervisor")

    def _route(state: AgentState) -> str:
        next_worker = state.get("next_worker")
        if next_worker == "FINISH" or not next_worker:
            return END
        return next_worker

    graph.add_conditional_edges("supervisor", _route)

    # 워커 완료 후 다시 supervisor로 (루프)
    graph.add_edge("MemoryWorker", "supervisor")
    graph.add_edge("SchedulerWorker", "supervisor")

    # GoogleWorker는 인증 필요 여부에 따라 분기
    def _after_google_worker(state: AgentState) -> str:
        if state.get("auth_request_url"):
            return "auth_interrupt"
        return "supervisor"

    graph.add_conditional_edges("GoogleWorker", _after_google_worker)

    # 인증 인터럽트 후 처리
    graph.add_conditional_edges("auth_interrupt", _route)

    return graph.compile(checkpointer=checkpointer)
