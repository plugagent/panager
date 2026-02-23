# src/panager/core/

Core infrastructure and shared utilities for the Panager application.

## Responsibility

This folder is responsible for:
- Centralized configuration management via Pydantic settings.
- Application-wide logging configuration using `structlog`.
- Defining base and domain-specific exception classes.

## Design

- **Type-Safe Configuration**: Leverages `pydantic-settings` to ensure all required environment variables are present and correctly typed at startup.
- **Structured Logging**: Uses `structlog` to provide consistent, searchable log entries.
- **Domain Exceptions**: Provides a clear exception hierarchy (`PanagerError`).

## Flow

1. **Setup**: The application entry point loads `Settings` from `config.py`.
2. **Configuration**: `configure_logging` is called with the settings.
3. **Runtime**: Other modules import `Settings` or raise exceptions from `exceptions.py`.

## Integration

- **config.py**: Used by almost all modules (DB, Bot, Agent, API).
- **logging.py**: Configures the global logging state.
- **exceptions.py**: Shared by `agent/` and `bot/` to communicate specific failure states.
