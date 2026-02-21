import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_memory_save_tool():
    with (
        patch("panager.memory.tool.save_memory", new_callable=AsyncMock) as mock_save,
        patch(
            "panager.memory.tool._get_embedding_async",
            new_callable=AsyncMock,
            return_value=[0.1] * 768,
        ),
    ):
        mock_save.return_value = "test-uuid"

        from panager.memory.tool import make_memory_save

        tool = make_memory_save(user_id=123)
        result = await tool.ainvoke({"content": "오늘 회의 참석"})
        assert "저장" in result
        mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_memory_search_tool():
    with (
        patch(
            "panager.memory.tool.search_memories", new_callable=AsyncMock
        ) as mock_search,
        patch(
            "panager.memory.tool._get_embedding_async",
            new_callable=AsyncMock,
            return_value=[0.1] * 768,
        ),
    ):
        mock_search.return_value = ["오늘 회의 참석"]

        from panager.memory.tool import make_memory_search

        tool = make_memory_search(user_id=123)
        result = await tool.ainvoke({"query": "회의", "limit": 5})
        assert "오늘 회의 참석" in result
