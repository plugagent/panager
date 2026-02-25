from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from panager.api.main import create_app


def test_health_check():
    mock_bot = MagicMock()
    app = create_app(mock_bot)
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
