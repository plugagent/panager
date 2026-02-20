import pytest
from uuid import UUID


@pytest.fixture(autouse=True)
async def setup_db():
    import os
    from panager.db.connection import init_pool, close_pool

    dsn = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://panager:panager@localhost:5433/panager_test"
    )
    await init_pool(dsn)
    from panager.db.connection import get_pool

    async with get_pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            999999,
            "test_user",
        )
    yield
    async with get_pool().acquire() as conn:
        await conn.execute("DELETE FROM memories WHERE user_id = $1", 999999)
        await conn.execute("DELETE FROM users WHERE user_id = $1", 999999)
    await close_pool()


@pytest.mark.asyncio
async def test_save_and_search_memory():
    from panager.memory.repository import save_memory, search_memories

    embedding = [0.1] * 768
    memory_id = await save_memory(999999, "오늘 회의 참석", embedding)
    assert isinstance(memory_id, UUID)

    results = await search_memories(999999, embedding, limit=5)
    assert len(results) >= 1
    assert "오늘 회의 참석" in results
