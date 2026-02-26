from __future__ import annotations
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from panager.agent.github.tools import make_github_tools


@pytest.fixture
def mock_github_service():
    service = MagicMock()
    service.settings = MagicMock()
    service.settings.github_webhook_secret = "test_secret"
    return service


@pytest.fixture
def mock_github_client():
    client = AsyncMock()
    # Mock for httpx.AsyncClient context manager
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    return client


@pytest.mark.asyncio
async def test_list_github_repositories_success(
    mock_github_service, mock_github_client
):
    user_id = 123
    mock_github_service.get_client = AsyncMock(return_value=mock_github_client)

    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "full_name": "owner/repo1",
            "description": "desc1",
            "html_url": "https://github.com/owner/repo1",
            "updated_at": "2026-02-27T12:00:00Z",
        }
    ]
    mock_response.raise_for_status = MagicMock()
    mock_github_client.get.return_value = mock_response

    tools = make_github_tools(user_id, mock_github_service)
    list_repos = next(t for t in tools if t.name == "list_github_repositories")

    result_str = await list_repos.ainvoke({})
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert len(result["repositories"]) == 1
    assert result["repositories"][0]["full_name"] == "owner/repo1"

    mock_github_client.get.assert_called_once_with(
        "/user/repos", params={"sort": "updated", "per_page": 20}
    )


@pytest.mark.asyncio
async def test_setup_github_webhook_success(mock_github_service, mock_github_client):
    user_id = 123
    mock_github_service.get_client = AsyncMock(return_value=mock_github_client)

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_github_client.post.return_value = mock_response

    tools = make_github_tools(user_id, mock_github_service)
    setup_webhook = next(t for t in tools if t.name == "setup_github_webhook")

    result_str = await setup_webhook.ainvoke(
        {"repo_full_name": "owner/repo1", "webhook_url": "https://example.com/webhook"}
    )
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert result["message"] == "Webhook created successfully"

    mock_github_client.post.assert_called_once()
    args, kwargs = mock_github_client.post.call_args
    assert args[0] == "/repos/owner/repo1/hooks"
    assert kwargs["json"]["config"]["url"] == "https://example.com/webhook"
    assert kwargs["json"]["config"]["secret"] == "test_secret"


@pytest.mark.asyncio
async def test_setup_github_webhook_error(mock_github_service, mock_github_client):
    user_id = 123
    mock_github_service.get_client = AsyncMock(return_value=mock_github_client)

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_github_client.post.return_value = mock_response

    tools = make_github_tools(user_id, mock_github_service)
    setup_webhook = next(t for t in tools if t.name == "setup_github_webhook")

    result_str = await setup_webhook.ainvoke(
        {"repo_full_name": "owner/repo1", "webhook_url": "https://example.com/webhook"}
    )
    result = json.loads(result_str)

    assert result["status"] == "error"
    assert result["message"] == "Bad Request"
