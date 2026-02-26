from __future__ import annotations

import json
import logging
import zoneinfo
from datetime import datetime
from typing import TYPE_CHECKING

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage,
)
from langchain_core.output_parsers import PydanticOutputParser

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
    """작업을 분배할 적절한 워커를 결정하거나 도구를 직접 호출합니다."""
    user_id = state["user_id"]
    # ... (timezone logic same)
    tz_name = state.get("timezone")
    if not tz_name:
        tz_name = await session_provider.get_user_timezone(user_id)
    # ... (rest of preamble)
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
        # 이미 discovery_node에서 OpenAI function 규격으로 변환됨
        llm = llm.bind_tools(discovered_tools)

    system_prompt = (
        "You are a supervisor managing a personal assistant bot. "
        "Your goal is to fulfill the user's request by calling appropriate tools or delegating to specialized workers.\n"
        f"Current Time: {now_str} ({tz_name})\n\n"
        "If you have tools available, use them to perform the task. "
        "If the task requires multiple steps, call tools one by one. "
        "If the request is fulfilled, respond to the user and finish.\n\n"
        "For complex legacy tasks, you can still refer to these specialists if needed:\n"
        "- GoogleWorker, GithubWorker, NotionWorker, MemoryWorker, SchedulerWorker.\n"
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

    # 메시지 트리밍 및 예약어 정제
    trimmed_messages = trim_agent_messages(
        state["messages"],
        max_tokens=settings.checkpoint_max_tokens,
    )

    if state.get("is_system_trigger"):
        system_prompt += "\n\nNote: This is an automated trigger (e.g., scheduled notification). Please handle it accordingly. (과거에 예약된 작업입니다. 사용자가 보낸 것처럼 자연스럽게 처리하세요.)"

    # 추가 컨텍스트 주입 (테스트 호환성 및 기능성 유지)
    task_summary = state.get("task_summary")
    if task_summary:
        system_prompt += f"\n\nRecent worker activity summary: {task_summary}"

    pending_reflections = state.get("pending_reflections")
    if pending_reflections:
        system_prompt += f"\n\nPending Reflections (GitHub changes needing review):\n{json.dumps(pending_reflections, indent=2)}"

    messages = [SystemMessage(content=system_prompt)] + trimmed_messages

    # ...

    response = await llm.ainvoke(messages)

    # LLM이 도구 호출을 선택한 경우
    res: dict = {"timezone": tz_name}
    if isinstance(response, AIMessage) and response.tool_calls:
        res["messages"] = [response]
        return res

    # 도구 호출이 없는 경우, 텍스트 응답이거나 라우팅 결정일 수 있음
    # 기존 Pydantic 파싱 로직을 유지하여 하위 호환성 확보
    # (단, 100+ 도구 시대에는 점진적으로 Pydantic 라우팅 대신 도구 호출로 넘어감)

    try:
        # JSON 형식인지 확인하여 워커 라우팅 시도
        if (
            response.content
            and isinstance(response.content, str)
            and "next_worker" in response.content
        ):
            parser = PydanticOutputParser(pydantic_object=Route)
            route = parser.parse(response.content)
            res.update({"next_worker": route.next_worker, "messages": [response]})
            return res
    except Exception:
        pass

    # 일반 응답인 경우 종료
    res.update({"next_worker": "FINISH", "messages": [response]})
    return res
