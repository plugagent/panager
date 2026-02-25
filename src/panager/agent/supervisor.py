from __future__ import annotations

import logging
import zoneinfo
from datetime import datetime
from typing import TYPE_CHECKING

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from panager.agent.state import AgentState, Route
from panager.agent.utils import WEEKDAY_KO, get_llm, trim_agent_messages

if TYPE_CHECKING:
    from panager.agent.interfaces import UserSessionProvider
    from panager.core.config import Settings


log = logging.getLogger(__name__)


async def supervisor_node(
    state: AgentState,
    settings: Settings,
    session_provider: UserSessionProvider,
) -> dict:
    """작업을 분배할 적절한 워커를 결정하거나 종료를 결정합니다."""
    user_id = state["user_id"]
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

    llm = get_llm(settings).with_structured_output(Route)

    system_prompt = (
        "You are a supervisor managing a personal assistant bot. Decide which specialist worker to call next or if the task is finished.\n"
        f"Current Time: {now_str} ({tz_name})\n\n"
        "Specialists:\n"
        "- GoogleWorker: Handles Google Calendar and Tasks (listing, creating, deleting).\n"
        "- MemoryWorker: Searches or saves user's personal information and context.\n"
        "- SchedulerWorker: Manages DM notifications and scheduled tasks.\n\n"
        "If the user's request is handled or no further action is needed, return 'FINISH'."
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
            id=last_msg.id,
            additional_kwargs=last_msg.additional_kwargs,
        )

    # 메시지 트리밍
    trimmed_messages = trim_agent_messages(
        state["messages"],
        max_tokens=settings.checkpoint_max_tokens,
    )

    if state.get("is_system_trigger"):
        system_prompt += "\n\nNote: This is an automated trigger (e.g., scheduled notification). Please handle it accordingly. (과거에 예약된 작업입니다. 사용자가 보낸 것처럼 자연스럽게 처리하세요.)"

    messages = [SystemMessage(content=system_prompt)] + trimmed_messages

    # 워커로부터의 요약 정보가 있으면 추가 컨텍스트 제공
    task_summary = state.get("task_summary")
    if task_summary:
        messages.append(
            SystemMessage(content=f"Recent worker activity summary: {task_summary}")
        )

    response = await llm.ainvoke(messages)
    assert isinstance(response, Route)

    res: dict = {"next_worker": response.next_worker}
    if "timezone" not in state:
        res["timezone"] = tz_name
    return res
