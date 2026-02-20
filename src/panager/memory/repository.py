from __future__ import annotations

from uuid import UUID

from panager.db.connection import get_pool


async def save_memory(user_id: int, content: str, embedding: list[float]) -> UUID:
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
        return UUID(str(row["id"]))


async def search_memories(
    user_id: int, embedding: list[float], limit: int = 5
) -> list[str]:
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
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM memories WHERE user_id = $1 AND id = $2",
            user_id,
            memory_id,
        )
