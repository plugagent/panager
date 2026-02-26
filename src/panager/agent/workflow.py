from __future__ import annotations

import functools
import json
import logging
from typing import TYPE_CHECKING, Literal

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from panager.agent.state import AgentState
from panager.agent.supervisor import supervisor_node
from panager.agent.utils import get_llm
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


def auth_interrupt_node(state: AgentState):
    """인증이 필요한 경우 실행을 일시 중단하고 사용자 승인을 기다립니다."""
    auth_url = state.get("auth_request_url")
    current_worker = state.get("next_worker")

    if auth_url:
        provider = "google"
        if "github.com" in auth_url:
            provider = "github"
        elif "notion.so" in auth_url or "api.notion.com" in auth_url:
            provider = "notion"

        resume_data = interrupt({"type": f"{provider}_auth_required", "url": auth_url})

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
                "auth_message_id": None,
                "next_worker": current_worker,
            }

        return {
            "auth_request_url": None,
            "next_worker": "FINISH",
        }
    return {}


async def discovery_node(state: AgentState, registry: ToolRegistry) -> dict:
    """사용자 메시지를 기반으로 관련 도구를 검색합니다."""
    last_msg = state["messages"][-1]
    if not isinstance(last_msg, HumanMessage) or not last_msg.content:
        return {}

    query = str(last_msg.content)
    clean_query = query.replace("[SCHEDULED_EVENT]", "").strip()

    tools = await registry.search_tools(clean_query, limit=10)
    discovered = []
    for t in tools:
        schema = {}
        if (
            hasattr(t, "args_schema")
            and t.args_schema
            and hasattr(t.args_schema, "schema")
        ):
            schema = t.args_schema.schema()

        discovered.append(
            {
                "name": t.name,
                "description": t.description,
                "schema": schema,
                "domain": (t.metadata.get("domain") if t.metadata else "unknown"),
            }
        )

    return {"discovered_tools": discovered}


async def tool_executor_node(
    state: AgentState,
    registry: ToolRegistry,
    google_service: GoogleService,
    github_service: GithubService,
    notion_service: NotionService,
) -> dict:
    """도구를 직접 실행하고 결과를 반환합니다. 인증이 필요한 경우 인터럽트를 발생시킵니다."""
    user_id = state["user_id"]
    last_message = state["messages"][-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {}

    user_tools = await registry.get_tools_for_user(
        user_id,
        google_service=google_service,
        github_service=github_service,
        notion_service=notion_service,
    )
    tool_map = {t.name: t for t in user_tools}

    tool_messages = []
    auth_url = None

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

            result = await tool.ainvoke(tool_call["args"])
            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call["id"])
            )
        except (GoogleAuthRequired, GithubAuthRequired, NotionAuthRequired):
            # 도메인별 서비스에서 인증 URL 획득
            tool_domain = (
                tool.metadata.get("domain")
                if tool and hasattr(tool, "metadata") and tool.metadata
                else None
            )

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
            elif "notion" in tool_call["name"] or tool_domain == "github":
                auth_url = notion_service.get_auth_url(user_id)

            tool_messages.append(
                ToolMessage(
                    content=json.dumps(
                        {"status": "error", "message": "Authentication required"},
                        ensure_ascii=False,
                    ),
                    tool_call_id=tool_call["id"],
                )
            )
            break

    res: dict = {"messages": tool_messages}
    if auth_url:
        res["auth_request_url"] = auth_url

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
        "supervisor",
        functools.partial(
            supervisor_node, settings=settings, session_provider=session_provider
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
    graph.add_edge("discovery", "supervisor")

    def _route(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tool_executor"

        next_worker = state.get("next_worker")
        if next_worker == "FINISH" or not next_worker:
            return END

        # 레거시 워커는 이제 개별 노드로 존재하지 않으므로 END로 처리하거나
        # 필요한 경우 다시 supervisor로 보낼 수 있음.
        # 여기서는 FINISH가 아니면 일단 END로 안전하게 처리
        return END

    graph.add_conditional_edges("supervisor", _route)

    def _after_tool_executor(state: AgentState) -> str:
        if state.get("auth_request_url"):
            return "auth_interrupt"
        return "supervisor"

    graph.add_conditional_edges("tool_executor", _after_tool_executor)
    graph.add_conditional_edges("auth_interrupt", _after_tool_executor)

    return graph.compile(checkpointer=checkpointer)
