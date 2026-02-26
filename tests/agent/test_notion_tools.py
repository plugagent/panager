from __future__ import annotations
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from panager.agent.notion.tools import make_notion_tools


@pytest.fixture
def mock_notion_service():
    return MagicMock()


@pytest.fixture
def mock_notion_client():
    client = AsyncMock()
    # Mock for pages.create
    client.pages = MagicMock()
    client.pages.create = AsyncMock()
    # Mock for search
    client.search = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_search_notion_success(mock_notion_service, mock_notion_client):
    user_id = 123
    mock_notion_service.get_client = AsyncMock(return_value=mock_notion_client)

    # Mock results: 1 database, 1 page
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
    assert result["results"][0]["id"] == "db_1"
    assert result["results"][0]["title"] == "Test Database"
    assert result["results"][1]["id"] == "pg_1"
    assert result["results"][1]["title"] == "Test Page"
    assert result["results"][2]["id"] == "pg_2"
    assert result["results"][2]["title"] == ""  # No title property found

    mock_notion_client.search.assert_called_once_with(
        query="test", filter={"value": "database", "property": "object"}
    )


@pytest.mark.asyncio
async def test_create_notion_page_success(mock_notion_service, mock_notion_client):
    user_id = 123
    mock_notion_service.get_client = AsyncMock(return_value=mock_notion_client)

    mock_notion_client.pages.create.return_value = {
        "id": "new_pg_1",
        "url": "https://notion.so/new_pg_1",
    }

    tools = make_notion_tools(user_id, mock_notion_service)
    create_notion_page = next(t for t in tools if t.name == "create_notion_page")

    properties = {"Name": {"title": [{"text": {"content": "New Page"}}]}}
    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": "Hello"}}]},
        }
    ]

    result_str = await create_notion_page.ainvoke(
        {"database_id": "db_1", "properties": properties, "children": children}
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["page_id"] == "new_pg_1"
    assert result["url"] == "https://notion.so/new_pg_1"

    mock_notion_client.pages.create.assert_called_once_with(
        parent={"database_id": "db_1"}, properties=properties, children=children
    )
