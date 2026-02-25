from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from panager.agent.notion.tools import make_notion_tools
from panager.agent.state import WorkerState
from panager.agent.utils import trim_agent_messages
from panager.core.exceptions import NotionAuthRequired

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI
    from langgraph.graph import CompiledGraph

    from panager.services.notion import NotionService


def build_notion_worker(
    llm: ChatOpenAI,
    notion_service: NotionService,
) -> CompiledGraph:
    """Notion 페이지 생성을 위한 전담 워커 서브 그래프를 생성합니다."""

    async def _worker_agent_node(state: WorkerState) -> dict:
        user_id = state["main_context"]["user_id"]
        tools = make_notion_tools(user_id, notion_service)
        llm_with_tools = llm.bind_tools(tools)

        system_prompt = (
            "당신은 Notion 관리를 담당하는 전문가입니다. "
            f"현재 작업: {state['task']}\n"
            "사용자의 요청에 따라 Notion 데이터베이스에서 정보를 검색하거나 새로운 페이지를 생성하세요. "
            "작업이 완료되면 수행한 내용을 간결하게 요약하여 보고하십시오."
        )
        trimmed_messages = trim_agent_messages(state["messages"], max_tokens=4000)
        messages = [SystemMessage(content=system_prompt)] + trimmed_messages
        response = await llm_with_tools.ainvoke(messages)

        res: dict = {"messages": [response]}
        if not response.tool_calls:
            res["task_summary"] = response.content

        return res

    async def _worker_tool_node(state: WorkerState) -> dict:
        user_id = state["main_context"]["user_id"]
        tools = make_notion_tools(user_id, notion_service)
        tool_map = {t.name: t for t in tools}
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {"messages": []}

        tool_messages = []
        auth_url = None
        pending_reflections = None

        for tool_call in last_message.tool_calls:
            try:
                result = await tool_map[tool_call["name"]].ainvoke(tool_call["args"])
                tool_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                )

                # 결과 파싱하여 pending_reflections이 있으면 추출
                try:
                    res_obj = json.loads(str(result))
                    if isinstance(res_obj, dict) and "pending_reflections" in res_obj:
                        pending_reflections = res_obj["pending_reflections"]
                except Exception:
                    pass
            except NotionAuthRequired:
                if user_id:
                    auth_url = notion_service.get_auth_url(user_id)

                tool_messages.append(
                    ToolMessage(
                        content=json.dumps(
                            {"status": "error", "message": "Notion 인증이 필요합니다."},
                            ensure_ascii=False,
                        ),
                        tool_call_id=tool_call["id"],
                    )
                )
                break

        res: dict = {"messages": tool_messages}
        if auth_url:
            res["auth_request_url"] = auth_url
        if pending_reflections is not None:
            res["pending_reflections"] = pending_reflections

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
