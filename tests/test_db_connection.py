import pytest


@pytest.mark.asyncio
async def test_init_and_close_pool():
    import os

    port = os.environ.get("POSTGRES_PORT", "5432")
    dsn = os.environ.get(
        "TEST_DATABASE_URL", f"postgresql://panager:panager@localhost:{port}/panager"
    )
    from panager.db.connection import init_pool, close_pool, get_pool

    await init_pool(dsn)
    pool = get_pool()
    assert pool is not None

    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    assert result == 1

    await close_pool()
