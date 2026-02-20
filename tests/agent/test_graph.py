import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.checkpoint.memory import MemorySaver


@pytest.mark.asyncio
async def test_graph_builds_successfully():
    from panager.agent.graph import build_graph

    graph = build_graph(MemorySaver())
    assert graph is not None


@pytest.mark.asyncio
async def test_graph_processes_message():
    from langchain_core.messages import AIMessage

    mock_llm_response = AIMessage(content="안녕하세요!")

    with patch("panager.agent.graph._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_get_llm.return_value = mock_llm

        from panager.agent.graph import build_graph

        graph = build_graph(MemorySaver())
        assert graph is not None
