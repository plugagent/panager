import logging
from unittest.mock import MagicMock


def test_configure_logging_adds_two_handlers():
    mock_settings = MagicMock()
    mock_settings.log_file_path = "/tmp/test_panager.log"
    mock_settings.log_max_bytes = 1_048_576
    mock_settings.log_backup_count = 3

    from panager.logging import configure_logging

    configure_logging(mock_settings)

    root_logger = logging.getLogger()
    handler_types = [type(h).__name__ for h in root_logger.handlers]
    assert "StreamHandler" in handler_types
    assert "RotatingFileHandler" in handler_types
