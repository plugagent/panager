from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from panager.agent.state import WorkerState

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI
    from langgraph.graph.graph import CompiledGraph


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
