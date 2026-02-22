from __future__ import annotations

import logging
from uuid import UUID

from panager.db.connection import get_pool
from panager.services.memory import MemoryService

log = logging.getLogger(__name__)

# NOTE: 이 모듈은 레거시입니다. 대신 panager.services.memory.MemoryService를 사용하세요.


async def save_memory(user_id: int, content: str, embedding: list[float]) -> UUID:
    """[LEGACY] 사용자의 메모리를 저장합니다."""
    # 직접 DB 작업을 수행하던 로직을 MemoryService로 점진적 이관 중
    # 여기서는 embedding을 이미 받았으므로 직접 저장 로직을 유지하거나
    # Service의 내부 메서드를 활용할 수 있습니다.
    # 일단은 호환성을 위해 직접 쿼리 로직을 유지하되, Service로의 전환을 권장합니다.
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO memories (user_id, content, embedding)
            VALUES ($1, $2, $3::vector)
            RETURNING id
            """,
            user_id,
            content,
            str(embedding),
        )
        if row is None:
            raise RuntimeError("메모리 저장 실패")
        return UUID(str(row["id"]))


async def search_memories(
    user_id: int, embedding: list[float], limit: int = 5
) -> list[str]:
    """[LEGACY] 메모리를 검색합니다."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT content
            FROM memories
            WHERE user_id = $1
            ORDER BY embedding <=> $2::vector
            LIMIT $3
            """,
            user_id,
            str(embedding),
            limit,
        )
        return [row["content"] for row in rows]


async def delete_memory(user_id: int, memory_id: UUID) -> None:
    """[LEGACY] 메모리를 삭제합니다."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM memories WHERE user_id = $1 AND id = $2",
            user_id,
            memory_id,
        )
