from __future__ import annotations
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from panager.agent.notion.tools import make_notion_tools


@pytest.fixture
def mock_notion_client():
    client = AsyncMock()
    client.pages = MagicMock()
    client.pages.create = AsyncMock()
    client.search = AsyncMock()
    return client


@pytest.fixture
def mock_notion_service(mock_notion_client):
    service = MagicMock()
    service.get_client = AsyncMock(return_value=mock_notion_client)
    return service


@pytest.mark.asyncio
async def test_search_notion_success(mock_notion_service, mock_notion_client):
    user_id = 123
    mock_notion_client.search.return_value = {
        "results": [
            {
                "id": "db_1",
                "object": "database",
                "title": [{"plain_text": "Test Database"}],
            },
            {
                "id": "pg_1",
                "object": "page",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Test Page"}]}
                },
            },
            {
                "id": "pg_2",
                "object": "page",
                "properties": {"Other": {"type": "rich_text", "rich_text": []}},
            },
        ]
    }

    tools = make_notion_tools(user_id, mock_notion_service)
    search_notion = next(t for t in tools if t.name == "search_notion")

    result_str = await search_notion.ainvoke(
        {"query": "test", "filter_type": "database"}
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert len(result["results"]) == 3
    assert result["results"][0]["title"] == "Test Database"
    assert result["results"][1]["title"] == "Test Page"
    assert result["results"][2]["title"] == ""

    mock_notion_client.search.assert_called_once_with(
        query="test", filter={"value": "database", "property": "object"}
    )


@pytest.mark.asyncio
async def test_search_notion_error(mock_notion_service, mock_notion_client):
    user_id = 123
    mock_notion_client.search.side_effect = Exception("Notion search failed")

    tools = make_notion_tools(user_id, mock_notion_service)
    search_notion = next(t for t in tools if t.name == "search_notion")

    with pytest.raises(Exception, match="Notion search failed"):
        await search_notion.ainvoke({"query": "test"})


@pytest.mark.asyncio
async def test_create_notion_page_success(mock_notion_service, mock_notion_client):
    user_id = 123
    mock_notion_client.pages.create.return_value = {
        "id": "new_pg_1",
        "url": "https://notion.so/new_pg_1",
    }

    tools = make_notion_tools(user_id, mock_notion_service)
    create_notion_page = next(t for t in tools if t.name == "create_notion_page")

    properties = {"Name": {"title": [{"text": {"content": "New Page"}}]}}
    children = [
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}
    ]
    result_str = await create_notion_page.ainvoke(
        {"database_id": "db_1", "properties": properties, "children": children}
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["page_id"] == "new_pg_1"
    mock_notion_client.pages.create.assert_called_once_with(
        parent={"database_id": "db_1"}, properties=properties, children=children
    )


@pytest.mark.asyncio
async def test_create_notion_page_error(mock_notion_service, mock_notion_client):
    user_id = 123
    mock_notion_client.pages.create.side_effect = Exception("Page creation failed")

    tools = make_notion_tools(user_id, mock_notion_service)
    create_notion_page = next(t for t in tools if t.name == "create_notion_page")

    with pytest.raises(Exception, match="Page creation failed"):
        await create_notion_page.ainvoke(
            {"database_id": "db_1", "properties": {"Name": {"title": []}}}
        )
