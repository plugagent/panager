import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from panager.api.main import create_app


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.google_service = MagicMock()
    bot.github_service = MagicMock()
    bot.notion_service = MagicMock()
    bot.google_service.get_auth_url.return_value = "https://google.com/auth"
    bot.github_service.get_auth_url.return_value = "https://github.com/auth"
    bot.notion_service.get_auth_url.return_value = "https://notion.so/auth"

    bot.google_service.exchange_code = AsyncMock()
    bot.github_service.exchange_code = AsyncMock()
    bot.notion_service.exchange_code = AsyncMock()

    bot.pending_messages = {123: "Pending message"}
    bot.auth_complete_queue = asyncio.Queue()
    return bot


@pytest.fixture
def app(mock_bot):
    return create_app(mock_bot)


@pytest.mark.asyncio
async def test_google_login(app, mock_bot):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/auth/google/login?user_id=123")
        assert response.status_code == 307
        assert response.headers["location"] == "https://google.com/auth"
        mock_bot.google_service.get_auth_url.assert_called_once_with(123)


@pytest.mark.asyncio
async def test_google_callback(app, mock_bot):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/auth/google/callback?code=abc&state=123")
        assert response.status_code == 200
        assert "Google 연동이 완료됐습니다" in response.text

        mock_bot.google_service.exchange_code.assert_awaited_once_with("abc", 123)

        # Check auth_complete_queue
        event = await mock_bot.auth_complete_queue.get()
        assert event["user_id"] == 123
        assert event["message"] == "Pending message"


@pytest.mark.asyncio
async def test_github_login(app, mock_bot):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/auth/github/login?user_id=123")
        assert response.status_code == 307
        assert response.headers["location"] == "https://github.com/auth"
        mock_bot.github_service.get_auth_url.assert_called_once_with(123)


@pytest.mark.asyncio
async def test_github_callback(app, mock_bot):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/auth/github/callback?code=abc&state=123")
        assert response.status_code == 200
        assert "GitHub 연동이 완료됐습니다" in response.text

        mock_bot.github_service.exchange_code.assert_awaited_once_with("abc", 123)

        event = await mock_bot.auth_complete_queue.get()
        assert event["user_id"] == 123


@pytest.mark.asyncio
async def test_notion_login(app, mock_bot):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/auth/notion/login?user_id=123")
        assert response.status_code == 307
        assert response.headers["location"] == "https://notion.so/auth"
        mock_bot.notion_service.get_auth_url.assert_called_once_with(123)


@pytest.mark.asyncio
async def test_notion_callback(app, mock_bot):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/auth/notion/callback?code=abc&state=123")
        assert response.status_code == 200
        assert "Notion 연동이 완료됐습니다" in response.text

        mock_bot.notion_service.exchange_code.assert_awaited_once_with("abc", 123)

        event = await mock_bot.auth_complete_queue.get()
        assert event["user_id"] == 123


@pytest.mark.asyncio
async def test_google_callback_error(app, mock_bot):
    mock_bot.google_service.exchange_code.side_effect = Exception("Exchange failed")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/auth/google/callback?code=abc&state=123")
        assert response.status_code == 400
        assert "Exchange failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_github_callback_error(app, mock_bot):
    mock_bot.github_service.exchange_code.side_effect = Exception("GH Exchange failed")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/auth/github/callback?code=abc&state=123")
        assert response.status_code == 400
        assert "GH Exchange failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_notion_callback_error(app, mock_bot):
    mock_bot.notion_service.exchange_code.side_effect = Exception(
        "Notion Exchange failed"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/auth/notion/callback?code=abc&state=123")
        assert response.status_code == 400
        assert "Notion Exchange failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_health_check(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
