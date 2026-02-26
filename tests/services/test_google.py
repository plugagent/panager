from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials

from panager.core.exceptions import GoogleAuthRequired
from panager.services.google import GoogleService, GoogleTokens


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.google_client_id = "test_client_id"
    settings.google_client_secret = "test_client_secret"
    settings.google_redirect_uri = "http://localhost/callback"
    return settings


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    # Mocking async context manager for pool.acquire()
    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = conn
    pool.acquire.return_value = context_manager
    return pool, conn


@pytest.fixture
def google_service(mock_settings, mock_pool):
    pool, _ = mock_pool
    return GoogleService(mock_settings, pool)


def test_google_tokens_dataclass():
    now = datetime.now(timezone.utc)
    tokens = GoogleTokens(
        user_id=123, access_token="access", refresh_token="refresh", expires_at=now
    )
    assert tokens.user_id == 123
    assert tokens.access_token == "access"
    assert tokens.refresh_token == "refresh"
    assert tokens.expires_at == now


def test_get_auth_url(google_service):
    with patch("panager.services.google.Flow") as mock_flow_cls:
        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow
        mock_flow.authorization_url.return_value = ("http://auth_url", "state")

        url = google_service.get_auth_url(123)

        assert url == "http://auth_url"
        mock_flow_cls.from_client_config.assert_called_once()
        mock_flow.authorization_url.assert_called_once_with(
            access_type="offline",
            include_granted_scopes="true",
            state="123",
            prompt="consent",
        )


@pytest.mark.asyncio
async def test_exchange_code(google_service):
    with patch("panager.services.google.Flow") as mock_flow_cls:
        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow
        mock_flow.credentials.token = "new_access"
        mock_flow.credentials.refresh_token = "new_refresh"

        with patch(
            "panager.services.google.GoogleService.save_tokens", new_callable=AsyncMock
        ) as mock_save:
            tokens = await google_service.exchange_code("test_code", 123)

            assert tokens["access_token"] == "new_access"
            assert tokens["refresh_token"] == "new_refresh"
            assert "expires_at" in tokens
            # fetch_token is called via asyncio.to_thread, but it's still a call to the mock
            mock_flow.fetch_token.assert_called_once_with(code="test_code")
            mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_exchange_code_no_refresh_token(google_service):
    with patch("panager.services.google.Flow") as mock_flow_cls:
        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow
        mock_flow.credentials.token = "new_access"
        mock_flow.credentials.refresh_token = None

        with pytest.raises(ValueError, match="refresh_token을 반환하지 않았습니다"):
            await google_service.exchange_code("test_code", 123)


@pytest.mark.asyncio
async def test_save_tokens(google_service, mock_pool):
    pool, conn = mock_pool
    tokens = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": datetime.now(timezone.utc),
    }

    await google_service.save_tokens(123, tokens)

    conn.execute.assert_called_once()
    args = conn.execute.call_args[0]
    # Check if user_id and tokens are passed correctly to the query
    # The order of arguments in save_tokens: user_id, access_token, refresh_token, expires_at
    assert args[1] == 123
    assert args[2] == "access"
    assert args[3] == "refresh"
    assert args[4] == tokens["expires_at"]


@pytest.mark.asyncio
async def test_get_tokens_success(google_service, mock_pool):
    pool, conn = mock_pool
    now = datetime.now(timezone.utc)
    conn.fetchrow.return_value = {
        "user_id": 123,
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": now,
    }

    tokens = await google_service.get_tokens(123)

    assert tokens is not None
    assert tokens.user_id == 123
    assert tokens.access_token == "access"
    assert tokens.refresh_token == "refresh"
    assert tokens.expires_at == now
    conn.fetchrow.assert_called_once_with(
        "SELECT * FROM google_tokens WHERE user_id = $1", 123
    )


@pytest.mark.asyncio
async def test_get_tokens_none(google_service, mock_pool):
    pool, conn = mock_pool
    conn.fetchrow.return_value = None

    tokens = await google_service.get_tokens(123)

    assert tokens is None


@pytest.mark.asyncio
async def test_update_access_token(google_service, mock_pool):
    pool, conn = mock_pool
    now = datetime.now(timezone.utc)

    await google_service.update_access_token(123, "new_access", now)

    conn.execute.assert_called_once()
    args = conn.execute.call_args[0]
    assert "UPDATE google_tokens" in args[0]
    assert args[1] == 123
    assert args[2] == "new_access"
    assert args[3] == now


@pytest.mark.asyncio
async def test_get_valid_credentials_not_found(google_service):
    with patch(
        "panager.services.google.GoogleService.get_tokens", new_callable=AsyncMock
    ) as mock_get_tokens:
        mock_get_tokens.return_value = None

        with pytest.raises(GoogleAuthRequired):
            await google_service._get_valid_credentials(123)


@pytest.mark.asyncio
async def test_get_valid_credentials_valid(google_service):
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=1)
    tokens = GoogleTokens(
        user_id=123, access_token="access", refresh_token="refresh", expires_at=future
    )

    with patch(
        "panager.services.google.GoogleService.get_tokens", new_callable=AsyncMock
    ) as mock_get_tokens:
        mock_get_tokens.return_value = tokens

        creds = await google_service._get_valid_credentials(123)

        assert isinstance(creds, Credentials)
        assert creds.token == "access"
        assert creds.refresh_token == "refresh"


@pytest.mark.asyncio
async def test_get_valid_credentials_expired(google_service):
    now = datetime.now(timezone.utc)
    past = now - timedelta(hours=1)
    tokens = GoogleTokens(
        user_id=123, access_token="old_access", refresh_token="refresh", expires_at=past
    )

    with patch(
        "panager.services.google.GoogleService.get_tokens", new_callable=AsyncMock
    ) as mock_get_tokens:
        mock_get_tokens.return_value = tokens
        with patch("panager.services.google.Credentials") as mock_creds_cls:
            mock_creds = MagicMock()
            mock_creds.token = "new_access"
            mock_creds_cls.return_value = mock_creds

            with patch(
                "panager.services.google.GoogleService.update_access_token",
                new_callable=AsyncMock,
            ) as mock_update:
                with patch("panager.services.google.Request"):
                    creds = await google_service._get_valid_credentials(123)

                    assert creds.token == "new_access"
                    # creds.refresh is called via asyncio.to_thread
                    mock_creds.refresh.assert_called_once()
                    mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_get_valid_credentials_expired_no_tz(google_service):
    # Test case where expires_at has no tzinfo (line 146-147)
    now = datetime.now(timezone.utc)
    past = (now - timedelta(hours=1)).replace(tzinfo=None)
    tokens = GoogleTokens(
        user_id=123, access_token="old_access", refresh_token="refresh", expires_at=past
    )

    with patch(
        "panager.services.google.GoogleService.get_tokens", new_callable=AsyncMock
    ) as mock_get_tokens:
        mock_get_tokens.return_value = tokens
        with patch("panager.services.google.Credentials") as mock_creds_cls:
            mock_creds = MagicMock()
            mock_creds.token = "new_access"
            mock_creds_cls.return_value = mock_creds
            with patch(
                "panager.services.google.GoogleService.update_access_token",
                new_callable=AsyncMock,
            ):
                with patch("panager.services.google.Request"):
                    creds = await google_service._get_valid_credentials(123)
                    assert creds.token == "new_access"


@pytest.mark.asyncio
async def test_get_valid_credentials_refresh_failed(google_service):
    now = datetime.now(timezone.utc)
    past = now - timedelta(hours=1)
    tokens = GoogleTokens(
        user_id=123, access_token="old_access", refresh_token="refresh", expires_at=past
    )

    with patch(
        "panager.services.google.GoogleService.get_tokens", new_callable=AsyncMock
    ) as mock_get_tokens:
        mock_get_tokens.return_value = tokens
        with patch("panager.services.google.Credentials") as mock_creds_cls:
            mock_creds = MagicMock()
            mock_creds.token = None  # Refresh failed to get new token
            mock_creds_cls.return_value = mock_creds

            with pytest.raises(RuntimeError, match="토큰 갱신 실패"):
                await google_service._get_valid_credentials(123)


@pytest.mark.asyncio
async def test_get_calendar_service(google_service):
    creds = MagicMock(spec=Credentials)
    with patch(
        "panager.services.google.GoogleService._get_valid_credentials",
        new_callable=AsyncMock,
    ) as mock_get_creds:
        mock_get_creds.return_value = creds
        with patch("panager.services.google.build") as mock_build:
            mock_build.return_value = MagicMock()

            service = await google_service.get_calendar_service(123)

            assert service is not None
            mock_build.assert_called_once_with("calendar", "v3", credentials=creds)


@pytest.mark.asyncio
async def test_get_tasks_service(google_service):
    creds = MagicMock(spec=Credentials)
    with patch(
        "panager.services.google.GoogleService._get_valid_credentials",
        new_callable=AsyncMock,
    ) as mock_get_creds:
        mock_get_creds.return_value = creds
        with patch("panager.services.google.build") as mock_build:
            mock_build.return_value = MagicMock()

            service = await google_service.get_tasks_service(123)

            assert service is not None
            mock_build.assert_called_once_with("tasks", "v1", credentials=creds)
