from __future__ import annotations

from typing import Annotated
from typing_extensions import NotRequired, TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    user_id: int
    username: str
    messages: Annotated[list, add_messages]
    memory_context: str
    is_system_trigger: NotRequired[bool]
    timezone: NotRequired[str]  # e.g. "Asia/Seoul", defaults to "Asia/Seoul" if absent


class WorkerState(TypedDict):
    user_id: int
    messages: Annotated[list, add_messages]
    auth_request_url: NotRequired[str]
