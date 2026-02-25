from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from panager.agent.state import WorkerState

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI
    from langgraph.graph import CompiledGraph


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
