from __future__ import annotations

import asyncio
import functools
import zoneinfo
from datetime import datetime
from functools import lru_cache
from typing import Any, Literal

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
from panager.config import Settings
from panager.google.auth import get_auth_url
from panager.google.credentials import GoogleAuthRequired
from panager.memory.tool import make_memory_save, make_memory_search
from panager.scheduler.tool import make_schedule_cancel, make_schedule_create


@lru_cache
def _get_settings() -> Settings:
    return Settings()


def _get_llm() -> ChatOpenAI:
    settings = _get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        streaming=True,
    )


def _build_tools(user_id: int, bot: Any = None) -> list:
    """user_id를 클로저로 포함한 tool 인스턴스 목록을 반환합니다."""
    from panager.google.tasks.tool import (
        make_task_complete,
        make_task_create,
        make_task_list,
    )
    from panager.google.calendar.tool import (
        make_event_create,
        make_event_delete,
        make_event_list,
        make_event_update,
    )

    return [
        make_memory_save(user_id),
        make_memory_search(user_id),
        make_schedule_create(user_id, bot),
        make_schedule_cancel(user_id),
        make_task_create(user_id),
        make_task_list(user_id),
        make_task_complete(user_id),
        make_event_list(user_id),
        make_event_create(user_id),
        make_event_update(user_id),
        make_event_delete(user_id),
    ]


_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


async def _agent_node(state: AgentState, bot: Any = None) -> dict:
    settings = _get_settings()
    user_id = state["user_id"]
    tz_name = state.get("timezone", "Asia/Seoul")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except zoneinfo.ZoneInfoNotFoundError:
        tz_name = "Asia/Seoul"
        tz = zoneinfo.ZoneInfo(tz_name)
    now = datetime.now(tz)
    weekday_ko = _WEEKDAY_KO[now.weekday()]
    utc_offset_raw = now.strftime("%z")  # e.g. "+0900"
    utc_offset = f"{utc_offset_raw[:3]}:{utc_offset_raw[3:]}"  # "+09:00"
    now_str = now.strftime(f"%Y년 %m월 %d일 ({weekday_ko}) %H:%M")

    tools = _build_tools(user_id, bot)
    llm = _get_llm().bind_tools(tools)
    system_prompt = (
        f"당신은 {state['username']}의 개인 매니저 패니저입니다. "
        "사용자의 할 일, 일정, 메모리를 관리하고 적극적으로 도와주세요.\n\n"
        f"현재 날짜/시간: {now_str} ({tz_name})\n"
        "날짜/시간 관련 요청은 반드시 위 현재 시각 기준으로 ISO 8601 형식으로 변환하세요. "
        f"예: {now.strftime('%Y')}-MM-DDTHH:MM:SS{utc_offset}\n\n"
        f"관련 메모리:\n{state.get('memory_context', '없음')}"
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
    return {"messages": [response]}


def _make_tool_node(bot):
    async def _tool_node(state: AgentState) -> dict:
        if not state["messages"]:
            return {"messages": []}
        user_id = state["user_id"]
        tools = _build_tools(user_id, bot)
        tool_map = {t.name: t for t in tools}

        last_message = state["messages"][-1]
        tool_messages: list[ToolMessage] = []

        for tool_call in last_message.tool_calls:
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
                    if bot is not None:
                        original = next(
                            (
                                m.content
                                for m in reversed(state["messages"])
                                if isinstance(m, HumanMessage)
                                and isinstance(m.content, str)
                            ),
                            "",
                        )
                        bot.pending_messages[user_id] = original
                    auth_url = get_auth_url(user_id)
                    result = (
                        f"Google 계정 연동이 필요합니다.\n"
                        f"아래 링크에서 연동해주세요:\n{auth_url}"
                    )
                except Exception as exc:
                    result = f"오류 발생: {exc}"

            tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

        return {"messages": tool_messages}

    return _tool_node


def _should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    if not state["messages"]:
        return END
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_graph(checkpointer, bot=None) -> object:
    graph = StateGraph(AgentState)
    agent_node = functools.partial(_agent_node, bot=bot)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", _make_tool_node(bot))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)
