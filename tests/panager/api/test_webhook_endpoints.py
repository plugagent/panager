import pytest
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, Request, HTTPException
from httpx import ASGITransport, AsyncClient
from panager.api.main import create_app
from panager.api.webhooks import verify_signature


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.trigger_task = AsyncMock()
    return bot


@pytest.fixture
def app(mock_bot):
    return create_app(mock_bot)


@pytest.mark.asyncio
async def test_verify_signature_valid():
    secret = "test_secret"
    body = b'{"hello": "world"}'
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    mock_request = AsyncMock(spec=Request)
    mock_request.body.return_value = body

    mock_settings = MagicMock()
    mock_settings.github_webhook_secret = secret

    with patch("panager.api.webhooks._get_settings", return_value=mock_settings):
        result = await verify_signature(mock_request, signature)
        assert result == body


@pytest.mark.asyncio
async def test_verify_signature_invalid():
    secret = "test_secret"
    body = b'{"hello": "world"}'
    signature = "sha256=invalid"

    mock_request = AsyncMock(spec=Request)
    mock_request.body.return_value = body

    mock_settings = MagicMock()
    mock_settings.github_webhook_secret = secret

    with patch("panager.api.webhooks._get_settings", return_value=mock_settings):
        with pytest.raises(HTTPException) as excinfo:
            await verify_signature(mock_request, signature)
        assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_signature_missing_header():
    mock_request = AsyncMock(spec=Request)
    with pytest.raises(HTTPException) as excinfo:
        await verify_signature(mock_request, None)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_github_webhook_success(app, mock_bot):
    secret = "test_secret"
    payload = {
        "repository": {"full_name": "owner/repo"},
        "ref": "refs/heads/main",
        "commits": [{"message": "feat: test", "timestamp": "2026-02-27T10:00:00Z"}],
    }
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    mock_settings = MagicMock()
    mock_settings.github_webhook_secret = secret

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.fetch.return_value = [{"user_id": 123}]

    with (
        patch("panager.api.webhooks._get_settings", return_value=mock_settings),
        patch("panager.api.webhooks.get_pool", return_value=mock_pool),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/webhooks/github",
                content=body,
                headers={"X-Hub-Signature-256": signature},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "success"
            assert response.json()["triggered_count"] == 1

            mock_bot.trigger_task.assert_awaited_once()
            args, kwargs = mock_bot.trigger_task.call_args
            assert args[0] == 123
            assert "GitHub Push 알림" in args[1]
            assert (
                kwargs["payload"]["pending_reflections"][0]["repository"]
                == "owner/repo"
            )


@pytest.mark.asyncio
async def test_github_webhook_ignored_missing_info(app, mock_bot):
    secret = "test_secret"
    payload = {"something": "else"}
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    mock_settings = MagicMock()
    mock_settings.github_webhook_secret = secret

    with patch("panager.api.webhooks._get_settings", return_value=mock_settings):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/webhooks/github",
                content=body,
                headers={"X-Hub-Signature-256": signature},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_github_webhook_no_users(app, mock_bot):
    secret = "test_secret"
    payload = {
        "repository": {"full_name": "owner/repo"},
        "ref": "refs/heads/main",
        "commits": [],
    }
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    mock_settings = MagicMock()
    mock_settings.github_webhook_secret = secret

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.fetch.return_value = []  # No users

    with (
        patch("panager.api.webhooks._get_settings", return_value=mock_settings),
        patch("panager.api.webhooks.get_pool", return_value=mock_pool),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/webhooks/github",
                content=body,
                headers={"X-Hub-Signature-256": signature},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ignored"
            assert response.json()["reason"] == "No registered users"
