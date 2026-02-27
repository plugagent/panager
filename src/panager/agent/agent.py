from __future__ import annotations

import json
import logging
import zoneinfo
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypedDict, NotRequired

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage,
    AnyMessage,
)

from panager.agent.state import AgentState
from panager.agent.utils import WEEKDAY_KO, get_llm, trim_agent_messages

if TYPE_CHECKING:
    from panager.agent.interfaces import UserSessionProvider
    from panager.core.config import Settings


log = logging.getLogger(__name__)


class AgentNodeOutput(TypedDict):
    """The output of the agent node."""

    messages: list[AnyMessage]
    timezone: str
    auth_request_url: NotRequired[None]
    auth_message_id: NotRequired[None]
    # next_worker is kept for legacy compatibility if needed, but will be set to FINISH
    next_worker: NotRequired[str]


async def agent_node(
    state: AgentState,
    settings: Settings,
    session_provider: UserSessionProvider,
) -> AgentNodeOutput:
    """사용자의 요청을 분석하여 도구를 호출하거나 응답을 생성합니다."""
    user_id = state["user_id"]

    # 타임존 설정
    tz_name = state.get("timezone")
    if not tz_name:
        tz_name = await session_provider.get_user_timezone(user_id)

    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz_name = "Asia/Seoul"
        tz = zoneinfo.ZoneInfo(tz_name)

    now = datetime.now(tz)
    weekday_ko = WEEKDAY_KO[now.weekday()]
    now_str = now.strftime(f"%Y년 %m월 %d일 ({weekday_ko}) %H:%M:%S")

    llm = get_llm(settings)

    # 검색된 도구들이 있으면 LLM에 바인딩
    discovered_tools = state.get("discovered_tools", [])
    if discovered_tools:
        # Pydantic 모델 리스트를 OpenAI 규격의 dict 리스트로 변환
        tool_schemas = [t.model_dump() for t in discovered_tools]
        llm = llm.bind_tools(tool_schemas)

    system_prompt = (
        "You are Panager, a helpful personal assistant bot. "
        "Your goal is to fulfill the user's request efficiently by using the available tools.\n"
        f"Current Time: {now_str} ({tz_name})\n\n"
        "If you have tools available, use them to perform the task. "
        "If the task requires multiple steps, call tools one by one. "
        "When the request is fulfilled or you have provided a final answer, stop and wait for the user.\n"
    )

    # 메시지 정리 (예약어 제거)
    last_msg = state["messages"][-1]
    if (
        isinstance(last_msg, HumanMessage)
        and isinstance(last_msg.content, str)
        and last_msg.content.startswith("[SCHEDULED_EVENT]")
    ):
        clean_content = last_msg.content.replace("[SCHEDULED_EVENT]", "").strip()
        state["messages"][-1] = HumanMessage(
            content=clean_content,
            id=getattr(last_msg, "id", None),
            additional_kwargs=getattr(last_msg, "additional_kwargs", {}),
        )

    # 메시지 트리밍
    trimmed_messages = trim_agent_messages(
        state["messages"],
        max_tokens=settings.checkpoint_max_tokens,
    )

    if state.get("is_system_trigger"):
        system_prompt += "\n\nNote: This is an automated trigger (e.g., scheduled notification). Please handle it accordingly. (과거에 예약된 작업입니다. 사용자가 보낸 것처럼 자연스럽게 처리하세요.)"

    # 추가 컨텍스트 주입
    task_summary = state.get("task_summary")
    if task_summary:
        system_prompt += f"\n\nRecent tool execution summary: {task_summary}"

    pending_reflections = state.get("pending_reflections")
    if pending_reflections:
        reflections_data = [r.model_dump() for r in pending_reflections]
        system_prompt += f"\n\nPending Reflections (GitHub changes needing review):\n{json.dumps(reflections_data, indent=2, ensure_ascii=False)}"

    messages = [SystemMessage(content=system_prompt)] + trimmed_messages

    response = await llm.ainvoke(messages)

    # 결과 구성
    res: AgentNodeOutput = {
        "timezone": tz_name,
        "messages": [response],
        "auth_request_url": None,
        "auth_message_id": None,
    }

    # 도구 호출이 없으면 종료로 간주
    if not (isinstance(response, AIMessage) and response.tool_calls):
        res["next_worker"] = "FINISH"

    return res
