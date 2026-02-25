from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.messages import AnyMessage, trim_messages
from langchain_openai import ChatOpenAI

if TYPE_CHECKING:
    from panager.core.config import Settings

log = logging.getLogger(__name__)

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def get_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        streaming=True,
    )


def trim_agent_messages(
    messages: list[AnyMessage], max_tokens: int
) -> list[AnyMessage]:
    """메시지 목록을 토큰 제한에 맞춰 트리밍합니다."""
    return trim_messages(
        messages,
        max_tokens=max_tokens,
        strategy="last",
        token_counter="approximate",
        include_system=False,
        allow_partial=False,
        start_on="human",
    )
