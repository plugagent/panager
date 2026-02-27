from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, TypedDict, NotRequired

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, AnyMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from panager.agent.state import AgentState, DiscoveredTool, FunctionSchema
from panager.agent.agent import agent_node
from panager.core.config import Settings
from panager.agent.registry import ToolRegistry
from panager.core.exceptions import (
    GoogleAuthRequired,
    GithubAuthRequired,
    NotionAuthRequired,
)

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph as CompiledGraph
    from panager.agent.interfaces import UserSessionProvider
    from panager.services.google import GoogleService
    from panager.services.github import GithubService
    from panager.services.notion import NotionService
    from panager.services.memory import MemoryService
    from panager.services.scheduler import SchedulerService


log = logging.getLogger(__name__)


class AuthInterruptOutput(TypedDict):
    """Output for the auth_interrupt node."""

    auth_request_url: None


def auth_interrupt_node(state: AgentState) -> AuthInterruptOutput:
    """단순하게 인터럽트를 발생시키고 사용자 인증 후의 데이터를 반환합니다."""
    auth_url = state.get("auth_request_url")
    provider = "service"
    if auth_url:
        if "github" in auth_url:
            provider = "github"
        elif "notion" in auth_url:
            provider = "notion"
        elif "google" in auth_url:
            provider = "google"

    # LangGraph 인터럽트 발생
    interrupt({"type": f"{provider}_auth_required", "url": auth_url})

    # 인증 완료 후 돌아오면 URL 정보 제거
    return {"auth_request_url": None}


async def discovery_node(
    state: AgentState, registry: ToolRegistry
) -> dict[str, list[DiscoveredTool]]:
    """사용자 메시지를 기반으로 관련 도구를 검색합니다."""
    messages = state.get("messages", [])
    if not messages:
        return {"discovered_tools": []}

    last_msg = messages[-1]
    if not isinstance(last_msg, HumanMessage) or not last_msg.content:
        return {"discovered_tools": []}

    query = str(last_msg.content)
    clean_query = query.replace("[SCHEDULED_EVENT]", "").strip()

    tools = await registry.search_tools(clean_query, limit=10)
    discovered: list[DiscoveredTool] = []
    for t in tools:
        # BaseTool.args는 이미 유효한 OpenAI parameters 형태의 dict를 반환합니다.
        schema = t.args if hasattr(t, "args") else {"type": "object", "properties": {}}

        # OpenAI function calling 규격에 맞게 변환하여 strict하게 생성
        discovered.append(
            DiscoveredTool(
                type="function",
                function=FunctionSchema(
                    name=t.name,
                    description=t.description,
                    parameters=schema,
                ),
                domain=(t.metadata.get("domain") if t.metadata else "unknown"),
            )
        )

    return {"discovered_tools": discovered}


class ToolExecutorOutput(TypedDict):
    """Output for the tool_executor node."""

    messages: list[AnyMessage]
    auth_request_url: NotRequired[str | None]


async def tool_executor_node(
    state: AgentState,
    registry: ToolRegistry,
    google_service: GoogleService,
    github_service: GithubService,
    notion_service: NotionService,
) -> ToolExecutorOutput:
    """도구를 직접 실행하고 결과를 반환합니다. 인증이 필요한 경우 인터럽트를 발생시킵니다."""
    user_id = state["user_id"]
    last_message = state["messages"][-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    user_tools = await registry.get_tools_for_user(
        user_id,
        google_service=google_service,
        github_service=github_service,
        notion_service=notion_service,
    )
    tool_map = {t.name: t for t in user_tools}

    tool_messages: list[AnyMessage] = []
    auth_url: str | None = None
    target_tool = None

    for tool_call in last_message.tool_calls:
        try:
            tool = tool_map.get(tool_call["name"])
            if not tool:
                tool_messages.append(
                    ToolMessage(
                        content=f"Tool {tool_call['name']} not found.",
                        tool_call_id=tool_call["id"],
                    )
                )
                continue

            target_tool = tool
            result = await tool.ainvoke(tool_call["args"])
            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call["id"])
            )
        except (GoogleAuthRequired, GithubAuthRequired, NotionAuthRequired):
            # 도메인별 서비스에서 인증 URL 획득
            tool_domain = None
            if (
                target_tool
                and hasattr(target_tool, "metadata")
                and target_tool.metadata
            ):
                tool_domain = target_tool.metadata.get("domain")

            if (
                tool_call["name"]
                in [
                    "manage_google_calendar",
                    "manage_google_tasks",
                ]
                or tool_domain == "google"
            ):
                auth_url = google_service.get_auth_url(user_id)
            elif "github" in tool_call["name"] or tool_domain == "github":
                auth_url = github_service.get_auth_url(user_id)
            elif "notion" in tool_call["name"] or tool_domain == "notion":
                auth_url = notion_service.get_auth_url(user_id)

            tool_messages.append(
                ToolMessage(
                    content="Authentication required. Please check the link.",
                    tool_call_id=tool_call["id"],
                )
            )
            break

    res: ToolExecutorOutput = {"messages": tool_messages, "auth_request_url": auth_url}
    return res


def build_graph(
    checkpointer: BaseCheckpointSaver,
    session_provider: UserSessionProvider,
    memory_service: MemoryService,
    google_service: GoogleService,
    github_service: GithubService,
    notion_service: NotionService,
    scheduler_service: SchedulerService,
    registry: ToolRegistry,
) -> CompiledGraph:
    settings = Settings()

    graph = StateGraph(AgentState)

    graph.add_node("discovery", functools.partial(discovery_node, registry=registry))
    graph.add_node(
        "agent",
        functools.partial(
            agent_node, settings=settings, session_provider=session_provider
        ),
    )
    graph.add_node("auth_interrupt", auth_interrupt_node)
    graph.add_node(
        "tool_executor",
        functools.partial(
            tool_executor_node,
            registry=registry,
            google_service=google_service,
            github_service=github_service,
            notion_service=notion_service,
        ),
    )

    graph.add_edge(START, "discovery")
    graph.add_edge("discovery", "agent")

    def _route(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tool_executor"

        next_worker = state.get("next_worker")
        if next_worker == "FINISH" or not next_worker:
            return END

        # 에이전트가 종료되지 않았으면 다시 discovery(또는 바로 agent)로 보낼 수 있지만
        # 보통은 도구 호출이 없으면 종료하는 것이 안전
        return END

    graph.add_conditional_edges("agent", _route)

    def _after_tool_executor(state: AgentState) -> str:
        if state.get("auth_request_url"):
            return "auth_interrupt"
        return "agent"

    graph.add_conditional_edges("tool_executor", _after_tool_executor)
    graph.add_conditional_edges("auth_interrupt", _after_tool_executor)

    return graph.compile(checkpointer=checkpointer)
