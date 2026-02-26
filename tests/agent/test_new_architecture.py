import pytest
from unittest.mock import AsyncMock, MagicMock
from panager.agent.registry import ToolRegistry
from panager.core.config import Settings
from langchain_core.tools import tool
from panager.agent.state import DiscoveredTool


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = AsyncMock()
    return pool


@pytest.fixture
def settings():
    settings = MagicMock(spec=Settings)
    return settings


@pytest.mark.asyncio
async def test_tool_registry_indexing_and_searching(mock_pool, settings):
    registry = ToolRegistry(mock_pool, settings)

    @tool
    def my_test_tool(arg1: str):
        """This is a tool for testing the registry."""
        return arg1

    # Manually add metadata
    my_test_tool.metadata = {"domain": "test"}

    registry.register_tools([my_test_tool])

    # Mock embedding generation
    with MagicMock() as mock_model:
        mock_model.encode.return_value = [0.1] * 768
        registry._model = mock_model

        # Mock DB response for search
        conn = mock_pool.acquire.return_value.__aenter__.return_value
        conn.fetch.return_value = [{"name": "my_test_tool"}]

        # Test sync (check if SQL is executed)
        await registry.sync_to_db()
        assert conn.execute.called

        # Test search
        results = await registry.search_tools("testing tool")
        assert len(results) == 1
        assert results[0].name == "my_test_tool"


@pytest.mark.asyncio
async def test_discovery_node_updates_state(mock_pool, settings):
    from panager.agent.workflow import discovery_node
    from langchain_core.messages import HumanMessage

    registry = MagicMock(spec=ToolRegistry)

    @tool
    def found_tool():
        """Found tool description."""
        pass

    found_tool.metadata = {"domain": "test"}

    registry.search_tools = AsyncMock(return_value=[found_tool])

    state = {"messages": [HumanMessage(content="find my tool")]}

    result = await discovery_node(state, registry)

    assert "discovered_tools" in result
    tool_info = result["discovered_tools"][0]
    assert isinstance(tool_info, DiscoveredTool)
    assert tool_info.function.name == "found_tool"
    assert tool_info.domain == "test"


@pytest.mark.asyncio
async def test_tool_executor_handles_auth_interrupt(mock_pool, settings):
    from panager.agent.workflow import tool_executor_node
    from panager.core.exceptions import GoogleAuthRequired
    from langchain_core.messages import AIMessage

    registry = MagicMock(spec=ToolRegistry)
    google_service = MagicMock()
    google_service.get_auth_url.return_value = "http://google-auth"

    mock_tool = MagicMock()
    mock_tool.name = "google_tool"
    mock_tool.metadata = {"domain": "google"}
    mock_tool.ainvoke.side_effect = GoogleAuthRequired()

    registry.get_tools_for_user = AsyncMock(return_value=[mock_tool])

    state = {
        "user_id": 123,
        "messages": [
            AIMessage(
                content="", tool_calls=[{"name": "google_tool", "args": {}, "id": "1"}]
            )
        ],
    }

    result = await tool_executor_node(
        state, registry, google_service, MagicMock(), MagicMock()
    )

    assert result["auth_request_url"] == "http://google-auth"
    assert result["messages"][0].tool_call_id == "1"
    assert "Authentication required" in result["messages"][0].content
