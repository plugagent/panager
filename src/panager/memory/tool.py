from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from panager.memory.repository import save_memory, search_memories

_model: SentenceTransformer | None = None


def _get_embedding(text: str) -> list[float]:
    """동기 임베딩 계산 — asyncio.to_thread()를 통해서만 호출할 것."""
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    return _model.encode(text).tolist()


async def _get_embedding_async(text: str) -> list[float]:
    """이벤트 루프를 블로킹하지 않는 비동기 임베딩 계산."""
    return await asyncio.to_thread(_get_embedding, text)


async def _warmup_embedding_model() -> None:
    """봇 시작 시 모델을 미리 로드해 첫 사용 시 cold start를 제거한다."""
    await _get_embedding_async("")


# ---------------------------------------------------------------------------
# Tool factories – user_id는 클로저로 포함, LLM에 노출되지 않음
# ---------------------------------------------------------------------------


class MemorySaveInput(BaseModel):
    content: str


class MemorySearchInput(BaseModel):
    query: str
    limit: int = 5


def make_memory_save(user_id: int) -> Any:
    @tool(args_schema=MemorySaveInput)
    async def memory_save(content: str) -> str:
        """중요한 내용을 장기 메모리에 저장합니다."""
        embedding = await _get_embedding_async(content)
        await save_memory(user_id, content, embedding)
        return f"메모리에 저장했습니다: {content[:50]}"

    return memory_save


def make_memory_search(user_id: int) -> Any:
    @tool(args_schema=MemorySearchInput)
    async def memory_search(query: str, limit: int = 5) -> str:
        """사용자의 과거 대화/패턴에서 관련 내용을 검색합니다."""
        embedding = await _get_embedding_async(query)
        results = await search_memories(user_id, embedding, limit)
        if not results:
            return "관련 메모리가 없습니다."
        return "\n".join(f"- {r}" for r in results)

    return memory_search
