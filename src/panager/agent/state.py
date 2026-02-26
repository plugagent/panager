from __future__ import annotations

from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class Route(BaseModel):
    """The next worker to call or FINISH."""

    next_worker: Literal[
        "GoogleWorker",
        "MemoryWorker",
        "SchedulerWorker",
        "GithubWorker",
        "NotionWorker",
        "FINISH",
    ] = Field(
        description="The next worker to handle the task, or 'FINISH' if the task is complete."
    )


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
    auth_message_id: NotRequired[int | None]  # Discord 메시지 ID 추적용
    task_summary: NotRequired[str]
    pending_reflections: NotRequired[list[dict]]
    discovered_tools: NotRequired[list[dict]]  # 검색된 도구 목록


class WorkerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    task: str
    main_context: dict
    auth_request_url: NotRequired[str | None]
    pending_reflections: NotRequired[list[dict]]
