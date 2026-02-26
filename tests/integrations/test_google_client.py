from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from panager.integrations.google_client import GoogleClient
from panager.core.exceptions import GoogleAuthRequired


@pytest.mark.asyncio
async def test_google_client_execute_success():
    client = GoogleClient()
    mock_request = MagicMock()
    mock_request.execute.return_value = {"status": "ok"}

    result = await client.execute(mock_request)

    assert result == {"status": "ok"}
    mock_request.execute.assert_called_once()


@pytest.mark.asyncio
async def test_google_client_execute_auth_error():
    client = GoogleClient()
    mock_request = MagicMock()

    # Mock HttpError for 401 Unauthorized
    resp = MagicMock()
    resp.status = 401
    mock_request.execute.side_effect = HttpError(resp, b"Unauthorized")

    with pytest.raises(GoogleAuthRequired):
        await client.execute(mock_request)


@pytest.mark.asyncio
async def test_google_client_execute_other_error():
    client = GoogleClient()
    mock_request = MagicMock()

    # Mock HttpError for 500 Internal Server Error
    resp = MagicMock()
    resp.status = 500
    mock_request.execute.side_effect = HttpError(resp, b"Internal Server Error")

    with pytest.raises(HttpError) as excinfo:
        await client.execute(mock_request)
    assert excinfo.value.resp.status == 500


@pytest.mark.asyncio
async def test_google_client_execute_list():
    client = GoogleClient()
    mock_collection = MagicMock()
    mock_request1 = MagicMock()
    mock_request2 = MagicMock()

    # First page
    mock_request1.execute.return_value = {"items": [{"id": "1"}, {"id": "2"}]}
    # Second page
    mock_request2.execute.return_value = {"items": [{"id": "3"}]}

    # Setup collection.list_next
    # First call returns mock_request2, second call returns None
    mock_collection.list_next.side_effect = [mock_request2, None]

    items = await client.execute_list(mock_collection, mock_request1, "items")

    assert len(items) == 3
    assert items == [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    assert mock_request1.execute.call_count == 1
    assert mock_request2.execute.call_count == 1
    assert mock_collection.list_next.call_count == 2
