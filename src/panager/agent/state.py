from __future__ import annotations

from typing import Annotated, Literal, NotRequired, TypedDict, Any
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class FunctionSchema(BaseModel):
    """OpenAI function calling schema."""

    name: str
    description: str
    parameters: dict[str, Any]


class DiscoveredTool(BaseModel):
    """Discovered tool information."""

    type: Literal["function"] = "function"
    function: FunctionSchema
    domain: str = "unknown"


class CommitInfo(BaseModel):
    """Information about a single commit."""

    message: str | None = None
    timestamp: str | None = None


class PendingReflection(BaseModel):
    """Information about a pending repository reflection."""

    repository: str
    ref: str
    commits: list[CommitInfo]


class AgentState(TypedDict):
    """The state of the agent."""

    user_id: int
    username: str
    messages: Annotated[list[AnyMessage], add_messages]
    memory_context: str
    is_system_trigger: NotRequired[bool]
    timezone: NotRequired[str]
    auth_request_url: NotRequired[str | None]
    auth_message_id: NotRequired[int | None]
    task_summary: NotRequired[str]
    pending_reflections: NotRequired[list[PendingReflection]]
    discovered_tools: NotRequired[list[DiscoveredTool]]
