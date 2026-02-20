from __future__ import annotations

from functools import lru_cache
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from panager.agent.state import AgentState
from panager.config import Settings
from panager.google.tool import task_complete, task_create, task_list
from panager.memory.tool import memory_save, memory_search
from panager.scheduler.tool import schedule_cancel, schedule_create

TOOLS = [
    memory_save,
    memory_search,
    schedule_create,
    schedule_cancel,
    task_create,
    task_list,
    task_complete,
]


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


def _agent_node(state: AgentState) -> dict:
    llm = _get_llm().bind_tools(TOOLS)
    system_prompt = (
        f"당신은 {state['username']}의 개인 매니저 패니저입니다. "
        "사용자의 할 일, 일정, 메모리를 관리하고 적극적으로 도와주세요.\n\n"
        f"관련 메모리:\n{state.get('memory_context', '없음')}"
    )
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def _should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_graph(checkpointer) -> object:
    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)
