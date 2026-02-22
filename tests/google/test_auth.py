from unittest.mock import patch, MagicMock


def test_get_auth_url():
    from panager.core.config import Settings

    mock_settings = MagicMock(spec=Settings)
    mock_settings.google_client_id = "test_client_id"
    mock_settings.google_client_secret = "test_secret"
    mock_settings.google_redirect_uri = "http://localhost/callback"

    with patch("panager.google.auth.get_settings", return_value=mock_settings):
        from panager.google.auth import get_auth_url

        url = get_auth_url(user_id=123)
        assert "accounts.google.com" in url
        assert "tasks" in url
        assert "123" in url
