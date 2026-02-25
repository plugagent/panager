from __future__ import annotations

import asyncio
import functools
import json
import logging
import zoneinfo
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from panager.agent.state import AgentState, WorkerState
from panager.core.config import Settings
from panager.core.exceptions import GoogleAuthRequired

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph import CompiledGraph
    from panager.agent.interfaces import UserSessionProvider
    from panager.services.google import GoogleService
    from panager.services.memory import MemoryService
    from panager.services.scheduler import SchedulerService


log = logging.getLogger(__name__)


def _get_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        streaming=True,
    )


def _build_tools(
    user_id: int,
    memory_service: MemoryService,
    google_service: GoogleService,
    scheduler_service: SchedulerService,
) -> list:
    """user_id를 클로저로 포함한 tool 인스턴스 목록을 반환합니다."""
    from panager.agent.tools import (
        make_manage_dm_scheduler,
        make_manage_google_calendar,
        make_manage_google_tasks,
        make_manage_user_memory,
    )

    return [
        make_manage_user_memory(user_id, memory_service),
        make_manage_dm_scheduler(user_id, scheduler_service),
        make_manage_google_tasks(user_id, google_service),
        make_manage_google_calendar(user_id, google_service),
    ]


_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


class Route(BaseModel):
    """The next worker to call or FINISH."""

    next_worker: Literal[
        "GoogleWorker", "MemoryWorker", "SchedulerWorker", "FINISH"
    ] = Field(
        description="The next worker to handle the task, or 'FINISH' if the task is complete."
    )


async def supervisor_node(
    state: AgentState,
    settings: Settings,
    session_provider: UserSessionProvider,
) -> dict:
    """작업을 분배할 적절한 워커를 결정하거나 종료를 결정합니다."""
    user_id = state["user_id"]
    tz_name = state.get("timezone")
    if not tz_name:
        tz_name = await session_provider.get_user_timezone(user_id)

    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz_name = "Asia/Seoul"
        tz = zoneinfo.ZoneInfo(tz_name)

    now = datetime.now(tz)
    weekday_ko = _WEEKDAY_KO[now.weekday()]
    now_str = now.strftime(f"%Y년 %m월 %d일 ({weekday_ko}) %H:%M:%S")

    llm = _get_llm(settings).with_structured_output(Route)

    system_prompt = (
        "You are a supervisor managing a personal assistant bot. Decide which specialist worker to call next or if the task is finished.\n"
        f"Current Time: {now_str} ({tz_name})\n\n"
        "Specialists:\n"
        "- GoogleWorker: Handles Google Calendar and Tasks (listing, creating, deleting).\n"
        "- MemoryWorker: Searches or saves user's personal information and context.\n"
        "- SchedulerWorker: Manages DM notifications and scheduled tasks.\n\n"
        "If the user's request is handled or no further action is needed, return 'FINISH'."
    )

    # 메시지 정리 (예약어 제거)
    last_msg = state["messages"][-1]
    if (
        isinstance(last_msg, HumanMessage)
        and isinstance(last_msg.content, str)
        and last_msg.content.startswith("[SCHEDULED_EVENT]")
    ):
        clean_content = last_msg.content.replace("[SCHEDULED_EVENT]", "").strip()
        state["messages"][-1] = HumanMessage(
            content=clean_content,
            id=last_msg.id,
            additional_kwargs=last_msg.additional_kwargs,
        )

    messages = [SystemMessage(content=system_prompt)] + state["messages"]

    # 워커로부터의 요약 정보가 있으면 추가 컨텍스트 제공
    task_summary = state.get("task_summary")
    if task_summary:
        messages.append(
            SystemMessage(content=f"Recent worker activity summary: {task_summary}")
        )

    response = await llm.ainvoke(messages)
    assert isinstance(response, Route)

    res: dict = {"next_worker": response.next_worker}
    if "timezone" not in state:
        res["timezone"] = tz_name
    return res


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


def build_google_worker(
    llm: ChatOpenAI,
    google_service: GoogleService,
    memory_service: MemoryService,
    scheduler_service: SchedulerService,
) -> CompiledGraph:
    """Google Calendar 및 Tasks 관리를 위한 전담 워커 서브 그래프를 생성합니다."""

    async def _worker_agent_node(state: WorkerState) -> dict:
        system_prompt = (
            "당신은 Google Calendar와 Google Tasks 관리를 담당하는 전문가입니다. "
            f"현재 작업: {state['task']}\n"
            "사용자의 요청에 따라 일정을 조회, 생성, 삭제하거나 할 일을 관리하세요. "
            "작업이 완료되면 수행한 내용을 간결하게 요약하여 보고하십시오."
        )
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = await llm.ainvoke(messages)

        res: dict = {"messages": [response]}
        # 도구 호출이 없으면 최종 응답으로 간주하고 요약을 상태에 저장
        if not response.tool_calls:
            res["task_summary"] = response.content

        return res

    async def _worker_tool_node(state: WorkerState) -> dict:
        user_id = state["main_context"]["user_id"]
        tools = _build_tools(user_id, memory_service, google_service, scheduler_service)
        tool_map = {t.name: t for t in tools}
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {"messages": []}

        tool_messages = []
        auth_url = None

        for tool_call in last_message.tool_calls:
            try:
                result = await tool_map[tool_call["name"]].ainvoke(tool_call["args"])
                tool_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                )
            except GoogleAuthRequired:
                # main_context에서 user_id를 추출하여 인증 URL 생성
                if user_id:
                    auth_url = google_service.get_auth_url(user_id)

                tool_messages.append(
                    ToolMessage(
                        content=json.dumps(
                            {"status": "error", "message": "Google 인증이 필요합니다."},
                            ensure_ascii=False,
                        ),
                        tool_call_id=tool_call["id"],
                    )
                )
                break  # 인증이 필요한 경우 추가 도구 실행 중단

        res: dict = {"messages": tool_messages}
        if auth_url:
            res["auth_request_url"] = auth_url

        return res

    def _worker_should_continue(state: WorkerState) -> Literal["tools", "__end__"]:
        if state.get("auth_request_url"):
            return END
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return END

    workflow = StateGraph(WorkerState)
    workflow.add_node("agent", _worker_agent_node)
    workflow.add_node("tools", _worker_tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", _worker_should_continue)
    workflow.add_edge("tools", "agent")

    return workflow.compile()


def build_memory_worker(llm: ChatOpenAI) -> CompiledGraph:
    """사용자 메모리 관리를 위한 워커 (Placeholder)"""

    async def _node(state: WorkerState) -> dict:
        content = "MemoryWorker logic placeholder. I can search or save info."
        return {
            "messages": [AIMessage(content=content)],
            "task_summary": "Memory task processed.",
        }

    workflow = StateGraph(WorkerState)
    workflow.add_node("agent", _node)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)
    return workflow.compile()


def build_scheduler_worker(llm: ChatOpenAI) -> CompiledGraph:
    """DM 알림 및 스케줄 관리를 위한 워커 (Placeholder)"""

    async def _node(state: WorkerState) -> dict:
        content = "SchedulerWorker logic placeholder. I can manage notifications."
        return {
            "messages": [AIMessage(content=content)],
            "task_summary": "Scheduler task processed.",
        }

    workflow = StateGraph(WorkerState)
    workflow.add_node("agent", _node)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)
    return workflow.compile()


def build_graph(
    checkpointer: BaseCheckpointSaver,
    session_provider: UserSessionProvider,
    memory_service: MemoryService,
    google_service: GoogleService,
    scheduler_service: SchedulerService,
) -> CompiledGraph:
    settings = Settings()
    llm = _get_llm(settings)

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
