from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from panager.agent.registry import ToolRegistry
from langchain_core.tools import tool


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = AsyncMock()
    return pool


@pytest.fixture
def settings():
    settings = MagicMock()
    return settings


@pytest.mark.asyncio
async def test_registry_model_loading_concurrency(mock_pool, settings):
    """모델 로딩 시 Lock이 작동하여 한 번만 로딩되는지 검증."""
    registry = ToolRegistry(mock_pool, settings)

    with patch("panager.agent.registry.SentenceTransformer") as mock_st:
        mock_instance = MagicMock()
        mock_st.return_value = mock_instance

        # 동시에 여러 번 호출
        results = await asyncio.gather(
            registry._get_model(), registry._get_model(), registry._get_model()
        )

        # SentenceTransformer는 한 번만 호출되어야 함
        mock_st.assert_called_once()
        assert all(r is mock_instance for r in results)


@pytest.mark.asyncio
async def test_registry_get_embedding_list_conversion(mock_pool, settings):
    """임베딩 결과가 numpy array 형태여도 list로 올바르게 변환되는지 검증."""
    registry = ToolRegistry(mock_pool, settings)

    with patch("panager.agent.registry.SentenceTransformer") as mock_st:
        mock_model = MagicMock()
        # tolist() 메서드를 가진 numpy-like object 시뮬레이션
        mock_embedding = MagicMock()
        mock_embedding.tolist.return_value = [0.1, 0.2, 0.3]
        mock_model.encode.return_value = mock_embedding
        registry._model = mock_model

        result = await registry._get_embedding("hello")
        assert result == [0.1, 0.2, 0.3]
        mock_embedding.tolist.assert_called_once()


@pytest.mark.asyncio
async def test_sync_tools_by_prototypes_no_schema(mock_pool, settings):
    """schema가 없는 도구도 정상적으로 동기화되는지 검증."""
    registry = ToolRegistry(mock_pool, settings)

    @tool
    def simple_tool():
        """No args tool."""
        pass

    # args_schema가 없는 상태 강제 (이미 @tool로 만들면 생기지만, 속성을 제거하여 테스트)
    if hasattr(simple_tool, "args_schema"):
        delattr(simple_tool, "args_schema")

    with patch.object(registry, "_get_embedding", return_value=[0.1] * 768):
        conn = mock_pool.acquire.return_value.__aenter__.return_value
        await registry.sync_tools_by_prototypes([simple_tool])

        # execute 호출 확인 (schema는 '{}'로 들어가야 함)
        args = conn.execute.call_args[0]
        assert args[4] == "{}"


@pytest.mark.asyncio
async def test_search_tools_missing_in_memory(mock_pool, settings):
    """DB에는 있지만 메모리 레지스트리에는 없는 도구에 대한 처리 검증."""
    registry = ToolRegistry(mock_pool, settings)

    with (
        patch.object(registry, "_get_embedding", return_value=[0.1] * 768),
        patch("panager.agent.registry.log") as mock_log,
    ):
        conn = mock_pool.acquire.return_value.__aenter__.return_value
        conn.fetch.return_value = [{"name": "unknown_tool"}]

        results = await registry.search_tools("query")

        assert len(results) == 0
        mock_log.warning.assert_called_once_with(
            "Tool found in DB but not in memory registry: %s", "unknown_tool"
        )


def test_registry_getters(mock_pool, settings):
    """get_tool 및 get_all_tools 기본 동작 검증."""
    registry = ToolRegistry(mock_pool, settings)

    @tool
    def tool_a():
        """A"""
        pass

    registry.register_tools([tool_a])

    assert registry.get_tool("tool_a") == tool_a
    assert registry.get_tool("non_existent") is None
    assert tool_a in registry.get_all_tools()
    assert len(registry.get_all_tools()) == 1
