from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from panager.agent.state import AgentState
from panager.config import Settings
from panager.google.auth import get_auth_url
from panager.google.tool import (
    GoogleAuthRequired,
    make_event_create,
    make_event_delete,
    make_event_list,
    make_event_update,
    make_task_complete,
    make_task_create,
    make_task_list,
)
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
    )


def _build_tools(user_id: int) -> list:
    """user_id를 클로저로 포함한 tool 인스턴스 목록을 반환합니다."""
    return [
        make_memory_save(user_id),
        make_memory_search(user_id),
        make_schedule_create(user_id),
        make_schedule_cancel(user_id),
        make_task_create(user_id),
        make_task_list(user_id),
        make_task_complete(user_id),
        make_event_list(user_id),
        make_event_create(user_id),
        make_event_update(user_id),
        make_event_delete(user_id),
    ]


async def _agent_node(state: AgentState) -> dict:
    user_id = state["user_id"]
    tools = _build_tools(user_id)
    llm = _get_llm().bind_tools(tools)
    system_prompt = (
        f"당신은 {state['username']}의 개인 매니저 패니저입니다. "
        "사용자의 할 일, 일정, 메모리를 관리하고 적극적으로 도와주세요.\n\n"
        f"관련 메모리:\n{state.get('memory_context', '없음')}"
    )
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = await llm.ainvoke(messages)
    return {"messages": [response]}


def _make_tool_node(bot):
    async def _tool_node(state: AgentState) -> dict:
        user_id = state["user_id"]
        tools = _build_tools(user_id)
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
                        original = state["messages"][0].content
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
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_graph(checkpointer, bot=None) -> object:
    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", _make_tool_node(bot))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)
