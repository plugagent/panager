from __future__ import annotations

import asyncio
import functools
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

from panager.agent.state import AgentState
from panager.core.config import Settings
from panager.core.exceptions import GoogleAuthRequired

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledGraph
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
        make_event_create,
        make_event_delete,
        make_event_list,
        make_event_update,
        make_memory_save,
        make_memory_search,
        make_schedule_cancel,
        make_schedule_create,
        make_task_delete,
        make_task_create,
        make_task_list,
        make_task_update,
    )

    return [
        make_memory_save(user_id, memory_service),
        make_memory_search(user_id, memory_service),
        make_schedule_create(user_id, scheduler_service),
        make_schedule_cancel(user_id, scheduler_service),
        make_task_create(user_id, google_service),
        make_task_list(user_id, google_service),
        make_task_update(user_id, google_service),
        make_task_delete(user_id, google_service),
        make_event_list(user_id, google_service),
        make_event_create(user_id, google_service),
        make_event_update(user_id, google_service),
        make_event_delete(user_id, google_service),
    ]


_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


async def _agent_node(
    state: AgentState,
    settings: Settings,
    session_provider: UserSessionProvider,
    memory_service: MemoryService,
    google_service: GoogleService,
    scheduler_service: SchedulerService,
) -> dict:
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
    tomorrow = now + timedelta(days=1)
    day_after_tomorrow = now + timedelta(days=2)
    day_after_day_after_tomorrow = now + timedelta(days=3)

    weekday_ko = _WEEKDAY_KO[now.weekday()]
    utc_offset_raw = now.strftime("%z")  # e.g. "+0900"
    utc_offset = f"{utc_offset_raw[:3]}:{utc_offset_raw[3:]}"  # "+09:00"
    now_str = now.strftime(f"%Y년 %m월 %d일 ({weekday_ko}) %H:%M:%S")

    relative_dates = (
        f"- 내일: {tomorrow.strftime('%Y-%m-%d')}\n"
        f"- 모레: {day_after_tomorrow.strftime('%Y-%m-%d')}\n"
        f"- 글피: {day_after_day_after_tomorrow.strftime('%Y-%m-%d')}"
    )

    tools = _build_tools(user_id, memory_service, google_service, scheduler_service)
    llm = _get_llm(settings).bind_tools(tools)
    system_prompt = (
        f"당신은 {state['username']}의 개인 매니저 패니저입니다. "
        "사용자의 할 일, 일정, 메모리를 관리하고 적극적으로 도와주세요.\n\n"
        f"현재 날짜/시간: {now_str} ({tz_name})\n"
        f"상대 날짜 정보:\n{relative_dates}\n\n"
        "날짜/시간 관련 요청은 반드시 위 현재 시각 및 상대 날짜 정보를 기준으로 ISO 8601 형식으로 변환하세요. "
        "만약 사용자가 시간(HH:MM)을 명시하지 않았다면 오전 9시(09:00:00)로 가정하십시오. "
        f"예: {now.strftime('%Y')}-MM-DDTHH:MM:SS{utc_offset}\n\n"
        f"관련 메모리:\n{state.get('memory_context', '없음')}\n\n"
        "참고: 모든 도구의 실행 결과는 JSON 데이터 구조로 제공됩니다. "
        "결과가 성공적(status: success)이라면 불필요한 재질문 없이 사용자에게 간결하게 보고하세요."
    )
    if state.get("is_system_trigger"):
        system_prompt += "\n\n이것은 과거에 예약된 작업입니다. 현재 상황을 확인하고 필요한 도구를 실행하십시오."

    # 마지막 사용자 메시지에서 예약어([SCHEDULED_EVENT]) 제거 (Spoofing 방지)
    last_msg = state["messages"][-1]
    if (
        isinstance(last_msg, HumanMessage)
        and isinstance(last_msg.content, str)
        and last_msg.content.startswith("[SCHEDULED_EVENT]")
    ):
        # 복사본 생성하여 원본 메시지 수정 (메타데이터는 유지하되 내용에서 접두사 제거)
        clean_content = last_msg.content.replace("[SCHEDULED_EVENT]", "").strip()
        state["messages"][-1] = HumanMessage(
            content=clean_content,
            id=last_msg.id,
            additional_kwargs=last_msg.additional_kwargs,
        )

    trimmed_messages = trim_messages(
        state["messages"],
        max_tokens=settings.checkpoint_max_tokens,
        strategy="last",
        token_counter="approximate",
        include_system=False,
        allow_partial=False,
        start_on="human",
    )
    messages = [SystemMessage(content=system_prompt)] + trimmed_messages
    response = await llm.ainvoke(messages)

    res: dict = {"messages": [response]}
    # state에 timezone이 없을 때만 추가하여 불필요한 덮어쓰기 방지
    if "timezone" not in state:
        res["timezone"] = tz_name

    return res


def _make_tool_node(
    session_provider: UserSessionProvider,
    memory_service: MemoryService,
    google_service: GoogleService,
    scheduler_service: SchedulerService,
):
    async def _tool_node(state: AgentState) -> dict:
        if not state["messages"]:
            return {"messages": []}
        user_id = state["user_id"]
        tools = _build_tools(user_id, memory_service, google_service, scheduler_service)
        tool_map = {t.name: t for t in tools}

        last_message = state["messages"][-1]
        tool_calls = last_message.tool_calls

        async def _invoke_tool(tool_call):
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            if tool_name not in tool_map:
                result = f"알 수 없는 툴: {tool_name}"
            else:
                try:
                    result = await tool_map[tool_name].ainvoke(tool_args)
                except GoogleAuthRequired:
                    # 원래 요청을 pending에 저장하고 인증 URL 안내
                    original = next(
                        (
                            m.content
                            for m in reversed(state["messages"])
                            if isinstance(m, HumanMessage)
                            and isinstance(m.content, str)
                        ),
                        "",
                    )
                    session_provider.pending_messages[user_id] = original
                    auth_url = google_service.get_auth_url(user_id)
                    result = (
                        f"Google 계정 연동이 필요합니다.\n"
                        f"아래 링크에서 연동해주세요:\n{auth_url}"
                    )
                except Exception as exc:
                    result = f"오류 발생: {exc}"

            return ToolMessage(content=str(result), tool_call_id=tool_id)

        # 모든 도구 호출을 병렬로 실행
        tool_messages = await asyncio.gather(*[_invoke_tool(tc) for tc in tool_calls])

        return {"messages": list(tool_messages)}

    return _tool_node


def _should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    if not state["messages"]:
        return END
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_graph(
    checkpointer: BaseCheckpointSaver,
    session_provider: UserSessionProvider,
    memory_service: MemoryService,
    google_service: GoogleService,
    scheduler_service: SchedulerService,
) -> CompiledGraph:
    settings = Settings()
    graph = StateGraph(AgentState)

    agent_node = functools.partial(
        _agent_node,
        settings=settings,
        session_provider=session_provider,
        memory_service=memory_service,
        google_service=google_service,
        scheduler_service=scheduler_service,
    )
    tool_node = _make_tool_node(
        session_provider, memory_service, google_service, scheduler_service
    )

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue)
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)
