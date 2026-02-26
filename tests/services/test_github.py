from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from panager.core.exceptions import GithubAuthRequired
from panager.services.github import GithubService, GithubTokens


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.github_client_id = "test_github_client_id"
    settings.github_client_secret = "test_github_client_secret"
    settings.github_redirect_uri = "http://localhost/github/callback"
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
def github_service(mock_settings, mock_pool):
    pool, _ = mock_pool
    return GithubService(mock_settings, pool)


def test_github_tokens_dataclass():
    now = datetime.now(timezone.utc)
    tokens = GithubTokens(
        user_id=123, access_token="access", refresh_token="refresh", expires_at=now
    )
    assert tokens.user_id == 123
    assert tokens.access_token == "access"
    assert tokens.refresh_token == "refresh"
    assert tokens.expires_at == now


def test_get_auth_url(github_service, mock_settings):
    user_id = 123
    url = github_service.get_auth_url(user_id)

    assert "github.com/login/oauth/authorize" in url
    assert f"client_id={mock_settings.github_client_id}" in url
    assert f"redirect_uri={mock_settings.github_redirect_uri}" in url
    assert f"state={user_id}" in url
    assert "scope=repo+admin%3Arepo_hook" in url or "scope=repo admin:repo_hook" in url


@pytest.mark.asyncio
async def test_exchange_code_success(github_service, mock_settings):
    code = "test_code"
    user_id = 123

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with patch(
            "panager.services.github.GithubService.save_tokens", new_callable=AsyncMock
        ) as mock_save:
            tokens = await github_service.exchange_code(code, user_id)

            assert tokens["access_token"] == "new_access_token"
            assert tokens["refresh_token"] == "new_refresh_token"
            assert tokens["expires_at"] is None

            mock_post.assert_called_once()
            mock_save.assert_called_once_with(user_id, tokens)


@pytest.mark.asyncio
async def test_exchange_code_with_expires_in(github_service):
    code = "test_code"
    user_id = 123

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "new_access_token",
        "expires_in": 3600,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with patch(
            "panager.services.github.GithubService.save_tokens", new_callable=AsyncMock
        ):
            tokens = await github_service.exchange_code(code, user_id)
            assert tokens["expires_at"] is not None
            # Check if it's approximately 1 hour from now
            expected_time = datetime.now(timezone.utc) + timedelta(seconds=3600)
            assert abs((tokens["expires_at"] - expected_time).total_seconds()) < 5


@pytest.mark.asyncio
async def test_exchange_code_error(github_service):
    code = "test_code"
    user_id = 123

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "error": "bad_verification_code",
        "error_description": "The code passed is incorrect or expired.",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(
            ValueError,
            match="GitHub OAuth error: The code passed is incorrect or expired.",
        ):
            await github_service.exchange_code(code, user_id)


@pytest.mark.asyncio
async def test_save_tokens(github_service, mock_pool):
    pool, conn = mock_pool
    user_id = 123
    tokens = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": datetime.now(timezone.utc),
    }

    await github_service.save_tokens(user_id, tokens)

    conn.execute.assert_called_once()
    args = conn.execute.call_args[0]
    assert args[1] == user_id
    assert args[2] == "access"
    assert args[3] == "refresh"
    assert args[4] == tokens["expires_at"]


@pytest.mark.asyncio
async def test_get_tokens_success(github_service, mock_pool):
    pool, conn = mock_pool
    user_id = 123
    now = datetime.now(timezone.utc)
    conn.fetchrow.return_value = {
        "user_id": user_id,
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": now,
    }

    tokens = await github_service.get_tokens(user_id)

    assert tokens is not None
    assert tokens.user_id == user_id
    assert tokens.access_token == "access"
    assert tokens.refresh_token == "refresh"
    assert tokens.expires_at == now
    conn.fetchrow.assert_called_once_with(
        "SELECT * FROM github_tokens WHERE user_id = $1", user_id
    )


@pytest.mark.asyncio
async def test_get_tokens_none(github_service, mock_pool):
    pool, conn = mock_pool
    conn.fetchrow.return_value = None

    tokens = await github_service.get_tokens(123)
    assert tokens is None


@pytest.mark.asyncio
async def test_get_client_success(github_service):
    user_id = 123
    mock_tokens = GithubTokens(
        user_id=user_id,
        access_token="test_access_token",
        refresh_token=None,
        expires_at=None,
    )

    with patch(
        "panager.services.github.GithubService.get_tokens", new_callable=AsyncMock
    ) as mock_get_tokens:
        mock_get_tokens.return_value = mock_tokens

        client = await github_service.get_client(user_id)

        assert isinstance(client, httpx.AsyncClient)
        assert (
            str(client.base_url) == "https://api.github.com"
            or str(client.base_url) == "https://api.github.com/"
        )
        assert client.headers["Authorization"] == "Bearer test_access_token"
        assert client.headers["Accept"] == "application/vnd.github.v3+json"
        await client.aclose()


@pytest.mark.asyncio
async def test_get_client_unauthorized(github_service):
    user_id = 123
    with patch(
        "panager.services.github.GithubService.get_tokens", new_callable=AsyncMock
    ) as mock_get_tokens:
        mock_get_tokens.return_value = None

        with pytest.raises(
            GithubAuthRequired, match="GitHub 계정이 연동되지 않았습니다."
        ):
            await github_service.get_client(user_id)
