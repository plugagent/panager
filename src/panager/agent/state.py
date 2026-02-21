from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import NotRequired, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    user_id: int
    username: str
    messages: Annotated[list[BaseMessage], add_messages]
    memory_context: str
    timezone: NotRequired[str]
    hitl_tool_call: NotRequired[dict[str, Any] | None]
