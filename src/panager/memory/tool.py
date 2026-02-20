from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from panager.memory.repository import save_memory, search_memories

_model: SentenceTransformer | None = None


def _get_embedding(text: str) -> list[float]:
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    return _model.encode(text).tolist()


# ---------------------------------------------------------------------------
# Tool factories – user_id is captured via closure, not exposed to the LLM
# ---------------------------------------------------------------------------


class MemorySaveInput(BaseModel):
    content: str


class MemorySearchInput(BaseModel):
    query: str
    limit: int = 5


def make_memory_save(user_id: int):
    @tool(args_schema=MemorySaveInput)
    async def memory_save(content: str) -> str:
        """중요한 내용을 장기 메모리에 저장합니다."""
        embedding = _get_embedding(content)
        await save_memory(user_id, content, embedding)
        return f"메모리에 저장했습니다: {content[:50]}"

    return memory_save


def make_memory_search(user_id: int):
    @tool(args_schema=MemorySearchInput)
    async def memory_search(query: str, limit: int = 5) -> str:
        """사용자의 과거 대화/패턴에서 관련 내용을 검색합니다."""
        embedding = _get_embedding(query)
        results = await search_memories(user_id, embedding, limit)
        if not results:
            return "관련 메모리가 없습니다."
        return "\n".join(f"- {r}" for r in results)

    return memory_search


# ---------------------------------------------------------------------------
# Standalone tool objects kept for backward compatibility
# ---------------------------------------------------------------------------


class _MemorySaveInputLegacy(BaseModel):
    content: str
    user_id: int


class _MemorySearchInputLegacy(BaseModel):
    query: str
    user_id: int
    limit: int = 5


@tool(args_schema=_MemorySaveInputLegacy)
async def memory_save(content: str, user_id: int) -> str:
    """중요한 내용을 장기 메모리에 저장합니다."""
    embedding = _get_embedding(content)
    await save_memory(user_id, content, embedding)
    return f"메모리에 저장했습니다: {content[:50]}"


@tool(args_schema=_MemorySearchInputLegacy)
async def memory_search(query: str, user_id: int, limit: int = 5) -> str:
    """사용자의 과거 대화/패턴에서 관련 내용을 검색합니다."""
    embedding = _get_embedding(query)
    results = await search_memories(user_id, embedding, limit)
    if not results:
        return "관련 메모리가 없습니다."
    return "\n".join(f"- {r}" for r in results)
