from __future__ import annotations

import json
import logging
from enum import Enum
from typing import TYPE_CHECKING

from langchain_core.tools import tool
from pydantic import BaseModel, model_validator

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

    from panager.services.memory import MemoryService

log = logging.getLogger(__name__)


class MemoryAction(str, Enum):
    SAVE = "save"
    SEARCH = "search"


class MemoryToolInput(BaseModel):
    action: MemoryAction
    content: str | None = None
    query: str | None = None
    limit: int = 5

    @model_validator(mode="after")
    def validate_action_fields(self) -> MemoryToolInput:
        if self.action == MemoryAction.SAVE and not self.content:
            raise ValueError("action='save' requires 'content'")
        if self.action == MemoryAction.SEARCH and not self.query:
            raise ValueError("action='search' requires 'query'")
        return self


def make_manage_user_memory(user_id: int, memory_service: MemoryService) -> BaseTool:
    @tool(args_schema=MemoryToolInput)
    async def manage_user_memory(
        action: MemoryAction,
        content: str | None = None,
        query: str | None = None,
        limit: int = 5,
    ) -> str:
        """사용자의 중요한 정보를 저장하거나 과거 메모리를 검색합니다.

        - action='save': content에 내용을 입력하여 저장합니다.
        - action='search': query에 검색어를 입력하여 관련 메모리를 찾습니다.
        """
        if action == MemoryAction.SAVE:
            # MemoryToolInput validation ensures content is present for SAVE
            await memory_service.save_memory(user_id, content)  # type: ignore
            return json.dumps(
                {
                    "status": "success",
                    "action": "save",
                    "content_preview": (content or "")[:50],
                },  # type: ignore
                ensure_ascii=False,
            )
        elif action == MemoryAction.SEARCH:
            # MemoryToolInput validation ensures query is present for SEARCH
            results = await memory_service.search_memories(user_id, query, limit)  # type: ignore
            return json.dumps(
                {"status": "success", "action": "search", "results": results},
                ensure_ascii=False,
            )
        raise ValueError(f"지원하지 않는 액션입니다: {action}")

    return manage_user_memory
