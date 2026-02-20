def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "test_token")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com")
    monkeypatch.setenv("LLM_API_KEY", "test_key")
    monkeypatch.setenv("LLM_MODEL", "minimax-m2.5-free")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost/callback")
    monkeypatch.setenv("LOG_FILE_PATH", "/tmp/test.log")

    from panager.config import Settings

    settings = Settings()
    assert settings.discord_token == "test_token"
    assert settings.llm_model == "minimax-m2.5-free"
    assert settings.postgres_port == 5432


def test_postgres_dsn_property(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "t")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("POSTGRES_USER", "panager")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "panager")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "cs")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost/callback")
    monkeypatch.setenv("LOG_FILE_PATH", "/tmp/test.log")

    from panager.config import Settings

    settings = Settings()
    assert "panager:secret@localhost:5432/panager" in settings.postgres_dsn
