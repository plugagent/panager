from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from panager.agent.google.tools import (
    make_manage_google_calendar,
    make_manage_google_tasks,
)
from panager.agent.state import WorkerState
from panager.agent.utils import trim_agent_messages
from panager.core.exceptions import GoogleAuthRequired

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI
    from langgraph.graph import CompiledGraph

    from panager.services.google import GoogleService


def build_google_worker(
    llm: ChatOpenAI,
    google_service: GoogleService,
) -> CompiledGraph:
    """Google Calendar 및 Tasks 관리를 위한 전담 워커 서브 그래프를 생성합니다."""

    async def _worker_agent_node(state: WorkerState) -> dict:
        system_prompt = (
            "당신은 Google Calendar와 Google Tasks 관리를 담당하는 전문가입니다. "
            f"현재 작업: {state['task']}\n"
            "사용자의 요청에 따라 일정을 조회, 생성, 삭제하거나 할 일을 관리하세요. "
            "작업이 완료되면 수행한 내용을 간결하게 요약하여 보고하십시오."
        )
        # 메시지 트리밍
        trimmed_messages = trim_agent_messages(
            state["messages"],
            max_tokens=4000,  # 워커별 적절한 한도 (설정에서 가져올 수도 있음)
        )
        messages = [SystemMessage(content=system_prompt)] + trimmed_messages

        user_id = state["main_context"]["user_id"]
        tools = [
            make_manage_google_tasks(user_id, google_service),
            make_manage_google_calendar(user_id, google_service),
        ]
        llm_with_tools = llm.bind_tools(tools)
        response = await llm_with_tools.ainvoke(messages)

        res: dict = {"messages": [response]}
        # 도구 호출이 없으면 최종 응답으로 간주하고 요약을 상태에 저장
        if not response.tool_calls:
            res["task_summary"] = response.content

        return res

    async def _worker_tool_node(state: WorkerState) -> dict:
        user_id = state["main_context"]["user_id"]
        # Google 워커에 필요한 도구만 생성
        tools = [
            make_manage_google_tasks(user_id, google_service),
            make_manage_google_calendar(user_id, google_service),
        ]
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
