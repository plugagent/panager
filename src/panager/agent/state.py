from __future__ import annotations

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    user_id: int
    username: str
    messages: Annotated[list, add_messages]
    memory_context: str
    timezone: str  # e.g. "Asia/Seoul"
