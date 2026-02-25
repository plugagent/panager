from __future__ import annotations

from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    user_id: int
    username: str
    messages: Annotated[list[AnyMessage], add_messages]
    memory_context: str
    is_system_trigger: NotRequired[bool]
    timezone: NotRequired[str]
    # New fields
    next_worker: NotRequired[str]
    auth_request_url: NotRequired[str | None]
    task_summary: NotRequired[str]


class WorkerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    task: str
    main_context: dict
    auth_request_url: NotRequired[str | None]
