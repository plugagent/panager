from __future__ import annotations

from typing import TYPE_CHECKING
from langchain_core.tools import tool
from pydantic import BaseModel

if TYPE_CHECKING:
    from panager.services.memory import MemoryService


# ---------------------------------------------------------------------------
# Tool factories – user_id is captured via closure, not exposed to the LLM
# ---------------------------------------------------------------------------


class MemorySaveInput(BaseModel):
    content: str


class MemorySearchInput(BaseModel):
    query: str
    limit: int = 5


def make_memory_save(user_id: int, memory_service: MemoryService):
    @tool(args_schema=MemorySaveInput)
    async def memory_save(content: str) -> str:
        """중요한 내용을 장기 메모리에 저장합니다."""
        await memory_service.save_memory(user_id, content)
        return f"메모리에 저장했습니다: {content[:50]}"

    return memory_save


def make_memory_search(user_id: int, memory_service: MemoryService):
    @tool(args_schema=MemorySearchInput)
    async def memory_search(query: str, limit: int = 5) -> str:
        """사용자의 과거 대화/패턴에서 관련 내용을 검색합니다."""
        results = await memory_service.search_memories(user_id, query, limit)
        if not results:
            return "관련 메모리가 없습니다."
        return "\n".join(f"- {r}" for r in results)

    return memory_search
