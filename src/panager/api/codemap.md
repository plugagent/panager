# src/panager/api/

FastAPI application for handling web-based interactions, specifically the Google OAuth flow.

## Responsibility

- Handle Google OAuth login and callback redirects.
- Provide a health check endpoint.
- Facilitate connection between OAuth flow and Discord bot.

## Design

- **FastAPI**: Used to build the web API.
- **Modular Routing**: `auth.py` contains auth-related routes.
- **Bot Integration**: App instance stores bot instance in `app.state.bot`.

## Flow

1. **Login Initiation**: User directed to `/auth/google/login`.
2. **Callback**: Google redirects to `/auth/google/callback`.
3. **Processing**: Handler exchanges code for tokens, notifies bot via queue.

## Integration

- **panager.bot.client**: Initializes and starts this FastAPI app.
- **panager.google**: Used for OAuth URL generation and code exchange.
