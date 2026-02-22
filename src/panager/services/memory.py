from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import asyncpg
from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)


class MemoryService:
    """장기 메모리 저장 및 검색을 담당하는 서비스."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        """SentenceTransformer 모델을 지연 로딩합니다."""
        if self._model is None:
            # CPU 집약적인 모델 로딩은 처음 사용할 때 수행
            self._model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
        return self._model

    async def _get_embedding(self, text: str) -> list[float]:
        """텍스트에 대한 임베딩을 비차단 방식으로 생성합니다."""
        model = self._get_model()
        # CPU 집약적인 인코딩 작업을 별도 스레드에서 실행하여 이벤트 루프 차단 방지
        embedding = await asyncio.to_thread(model.encode, text)
        return embedding.tolist()

    async def save_memory(self, user_id: int, content: str) -> UUID:
        """사용자의 메모리를 임베딩과 함께 저장합니다."""
        embedding = await self._get_embedding(content)
        async with self._pool.acquire() as conn:
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
        self, user_id: int, query: str, limit: int = 5
    ) -> list[str]:
        """쿼리와 유사한 사용자의 메모리를 검색합니다."""
        embedding = await self._get_embedding(query)
        async with self._pool.acquire() as conn:
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

    async def delete_memory(self, user_id: int, memory_id: UUID) -> None:
        """특정 메모리를 삭제합니다."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM memories WHERE user_id = $1 AND id = $2",
                user_id,
                memory_id,
            )
