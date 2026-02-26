import pytest


@pytest.mark.asyncio
async def test_init_and_close_pool():
    import os

    dsn = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://panager:panager@localhost:5432/panager"
    )
    from panager.db.connection import init_pool, close_pool, get_pool

    await init_pool(dsn)
    pool = get_pool()
    assert pool is not None

    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    assert result == 1

    await close_pool()
