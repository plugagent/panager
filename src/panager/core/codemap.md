# src/panager/core/

Core infrastructure and cross-cutting concerns for the Panager application.

## Responsibility
- **Configuration Management**: Centralized, type-safe settings via Pydantic.
- **Observability**: Structured logging and diagnostics.
- **Error Handling**: Defines the global exception hierarchy.

## Design Patterns
- **Singleton Settings**: `Settings` class using `pydantic-settings` for environment variable mapping and validation.
- **Structured Logging**: Uses `structlog` for machine-readable logs, facilitating easier debugging in complex agentic workflows.
- **Exception Hierarchy**: Implements `PanagerError` base class with specialized domain exceptions (e.g., `GoogleAuthRequired`, `GithubAuthRequired`).

## Data & Control Flow
1. **Bootstrap**: `main.py` initializes `Settings` and calls `configure_logging`.
2. **Runtime Configuration**: Modules import `Settings` to access environment variables.
3. **Error Propagation**: Services and agents raise specialized exceptions which are caught by the Discord handler or Graph nodes to manage flow (e.g., triggering OAuth interrupts).

## Integration Points
- **Infrastructure**: Used by every package in the system (`agent`, `services`, `discord`, `api`, `db`).
- **External Environment**: Maps OS environment variables to application-level configuration.
