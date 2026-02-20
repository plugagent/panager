from __future__ import annotations

from uuid import UUID

from panager.db.connection import get_pool


def _format_embedding(embedding: list[float]) -> str:
    """부동소수점 벡터를 pgvector 호환 텍스트 형식으로 변환."""
    return "[" + ",".join(repr(x) for x in embedding) + "]"


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
            _format_embedding(embedding),
        )
        if row is None:
            raise RuntimeError(
                "INSERT INTO memories RETURNING id가 행을 반환하지 않았습니다."
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
            _format_embedding(embedding),
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
