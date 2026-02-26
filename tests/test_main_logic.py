from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from panager.main import _cleanup_old_checkpoints, _ttl_cutoff_uuid, main


def test_ttl_cutoff_uuid():
    # Test with 7 days TTL
    ttl_days = 7
    cutoff_str = _ttl_cutoff_uuid(ttl_days)

    # Verify it's a valid UUID
    val = uuid.UUID(cutoff_str)
    assert str(val) == cutoff_str
    assert val.version == 7


@pytest.mark.asyncio
async def test_cleanup_old_checkpoints():
    mock_conn = AsyncMock()
    ttl_days = 30

    await _cleanup_old_checkpoints(mock_conn, ttl_days)

    # Verify DELETE queries were called
    assert mock_conn.execute.call_count == 3
    calls = mock_conn.execute.call_args_list

    # Check if DELETE FROM checkpoint_writes was called
    assert any("DELETE FROM checkpoint_writes" in call[0][0] for call in calls)
    assert any("DELETE FROM checkpoints" in call[0][0] for call in calls)
    assert any("DELETE FROM checkpoint_blobs" in call[0][0] for call in calls)


@pytest.mark.asyncio
async def test_main_orchestration():
    # Mock all major components in main.py
    with (
        patch("panager.main.Settings") as mock_settings_cls,
        patch("panager.main.init_pool", new_callable=AsyncMock) as mock_init_pool,
        patch(
            "panager.main.psycopg.AsyncConnection.connect", new_callable=AsyncMock
        ) as mock_pg_connect,
        patch("panager.main.AsyncPostgresSaver") as mock_saver_cls,
        patch("panager.main.build_graph") as mock_build_graph,
        patch("panager.main.create_app") as mock_create_app,
        patch("panager.main.uvicorn.Server") as mock_server_cls,
        patch("panager.main.PanagerBot") as mock_bot_cls,
        patch("panager.agent.registry.ToolRegistry") as mock_registry_cls,
        patch("panager.main.configure_logging"),
        patch("panager.main.os.makedirs"),
        patch("panager.main.close_pool", new_callable=AsyncMock) as mock_close_pool,
        patch("panager.main.SchedulerService") as mock_scheduler_service_cls,
    ):
        # Setup mocks
        mock_registry = MagicMock()
        mock_registry.sync_to_db = AsyncMock()
        mock_registry_cls.return_value = mock_registry
        mock_settings = MagicMock()
        mock_settings.log_file_path = "/tmp/panager.log"
        mock_settings.postgres_dsn_asyncpg = "postgresql://user:pass@host:5432/db"
        mock_settings.checkpoint_ttl_days = 7
        mock_settings.discord_token = "fake-token"
        mock_settings_cls.return_value = mock_settings

        mock_pg_conn = AsyncMock()
        mock_pg_connect.return_value = mock_pg_conn

        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock()
        mock_saver_cls.return_value = mock_saver

        mock_bot = AsyncMock()
        mock_bot.__aenter__.return_value = mock_bot
        # Make bot.start raise CancelledError to simulate shutdown
        mock_bot.start.side_effect = asyncio.CancelledError
        mock_bot_cls.return_value = mock_bot

        mock_server = MagicMock()
        mock_server.serve = AsyncMock()
        mock_server_cls.return_value = mock_server

        mock_scheduler_service = MagicMock()
        mock_scheduler_service.restore_schedules = AsyncMock()
        mock_scheduler_service_cls.return_value = mock_scheduler_service

        # Execute main
        await main()

        # Verify calls
        mock_settings_cls.assert_called_once()
        mock_init_pool.assert_called_once_with(mock_settings.postgres_dsn_asyncpg)
        mock_pg_connect.assert_called_once()
        mock_saver.setup.assert_called_once()
        mock_build_graph.assert_called_once()
        mock_create_app.assert_called_once_with(mock_bot)
        mock_server_cls.assert_called_once()
        mock_bot.start.assert_called_once_with(mock_settings.discord_token)

        # Verify cleanup
        mock_pg_conn.close.assert_called_once()
        mock_close_pool.assert_called_once()
