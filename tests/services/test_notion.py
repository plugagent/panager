from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from panager.core.exceptions import NotionAuthRequired
from panager.services.notion import NotionService, NotionTokens


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.notion_client_id = "test_notion_client_id"
    settings.notion_client_secret = "test_notion_client_secret"
    settings.notion_redirect_uri = "http://localhost/notion/callback"
    return settings


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = conn
    pool.acquire.return_value = context_manager
    return pool, conn


@pytest.fixture
def notion_service(mock_settings, mock_pool):
    pool, _ = mock_pool
    return NotionService(mock_settings, pool)


def test_notion_tokens_dataclass():
    tokens = NotionTokens(
        user_id=123,
        access_token="access",
        workspace_id="ws_123",
        workspace_name="My WS",
        bot_id="bot_123",
    )
    assert tokens.user_id == 123
    assert tokens.access_token == "access"
    assert tokens.workspace_id == "ws_123"
    assert tokens.workspace_name == "My WS"
    assert tokens.bot_id == "bot_123"


def test_get_auth_url(notion_service, mock_settings):
    from urllib.parse import quote

    user_id = 123
    url = notion_service.get_auth_url(user_id)

    assert "api.notion.com/v1/oauth/authorize" in url
    assert f"client_id={mock_settings.notion_client_id}" in url
    assert f"redirect_uri={quote(mock_settings.notion_redirect_uri, safe='')}" in url
    assert f"state=notion_{user_id}" in url
    assert "response_type=code" in url
    assert "owner=user" in url


@pytest.mark.asyncio
async def test_exchange_code_success(notion_service, mock_settings):
    code = "test_code"
    user_id = 123

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "new_access_token",
        "workspace_id": "ws_123",
        "workspace_name": "My Workspace",
        "bot_id": "bot_123",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with patch(
            "panager.services.notion.NotionService.save_tokens", new_callable=AsyncMock
        ) as mock_save:
            tokens = await notion_service.exchange_code(code, user_id)

            assert tokens["access_token"] == "new_access_token"
            assert tokens["workspace_id"] == "ws_123"

            mock_post.assert_called_once()
            # Verify auth headers for Notion (Basic Auth)
            args, kwargs = mock_post.call_args
            assert kwargs["auth"] == (
                mock_settings.notion_client_id,
                mock_settings.notion_client_secret,
            )

            mock_save.assert_called_once_with(user_id, tokens)


@pytest.mark.asyncio
async def test_exchange_code_error(notion_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "error": "invalid_grant",
        "error_description": "The provided authorization grant is invalid",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with pytest.raises(
            ValueError,
            match="Notion OAuth error: The provided authorization grant is invalid",
        ):
            await notion_service.exchange_code("bad_code", 123)


@pytest.mark.asyncio
async def test_save_tokens(notion_service, mock_pool):
    pool, conn = mock_pool
    user_id = 123
    tokens = {
        "access_token": "access",
        "workspace_id": "ws_123",
    }

    await notion_service.save_tokens(user_id, tokens)

    conn.execute.assert_called_once()
    args = conn.execute.call_args[0]
    assert args[1] == user_id
    assert args[2] == "access"
    assert args[3] == "ws_123"


@pytest.mark.asyncio
async def test_get_tokens_success(notion_service, mock_pool):
    pool, conn = mock_pool
    user_id = 123
    conn.fetchrow.return_value = {
        "user_id": user_id,
        "access_token": "access",
        "workspace_id": "ws_123",
    }

    tokens = await notion_service.get_tokens(user_id)

    assert tokens is not None
    assert tokens.user_id == user_id
    assert tokens.access_token == "access"
    assert tokens.workspace_id == "ws_123"
    assert tokens.workspace_name is None  # Not stored in DB
    assert tokens.bot_id is None  # Not stored in DB
    conn.fetchrow.assert_called_once_with(
        "SELECT * FROM notion_tokens WHERE user_id = $1", user_id
    )


@pytest.mark.asyncio
async def test_get_tokens_none(notion_service, mock_pool):
    pool, conn = mock_pool
    conn.fetchrow.return_value = None

    tokens = await notion_service.get_tokens(123)
    assert tokens is None


@pytest.mark.asyncio
async def test_get_client_success(notion_service):
    user_id = 123
    mock_tokens = NotionTokens(
        user_id=user_id,
        access_token="test_access_token",
        workspace_id="ws_123",
        workspace_name=None,
        bot_id=None,
    )

    with patch(
        "panager.services.notion.NotionService.get_tokens", new_callable=AsyncMock
    ) as mock_get_tokens:
        mock_get_tokens.return_value = mock_tokens

        with patch("panager.services.notion.AsyncClient") as mock_client_cls:
            await notion_service.get_client(user_id)
            mock_client_cls.assert_called_once_with(auth="test_access_token")


@pytest.mark.asyncio
async def test_get_client_unauthorized(notion_service):
    user_id = 123
    with patch(
        "panager.services.notion.NotionService.get_tokens", new_callable=AsyncMock
    ) as mock_get_tokens:
        mock_get_tokens.return_value = None

        with pytest.raises(
            NotionAuthRequired, match="Notion 계정이 연동되지 않았습니다."
        ):
            await notion_service.get_client(user_id)
