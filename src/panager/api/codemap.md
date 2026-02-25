# src/panager/api/

FastAPI application serving as the web-facing interface for external integrations and OAuth flows.

## Responsibility
- **OAuth Management**: Handles login and callback redirects for Google, GitHub, and Notion.
- **Webhook Ingestion**: Receives and validates GitHub push events to trigger proactive agent tasks.
- **Infrastructure**: Provides health checks and bridges web-based events to the Discord bot via shared state and queues.

## Design Patterns
- **Modular Routing**: Uses `APIRouter` to isolate `auth` and `webhook` logic.
- **Signature Verification**: Implements HMAC-SHA256 validation for GitHub webhooks to ensure request authenticity.
- **Shared State Bridge**: Uses `app.state.bot` to directly access the running Discord bot instance for triggering agent workflows.

## Data & Control Flow
1. **OAuth Flow**: User navigates to `/auth/{provider}/login` -> Redirects to provider -> Callback to `/auth/{provider}/callback` -> Token exchange -> Signal bot via `auth_complete_queue`.
2. **Webhook Flow**: GitHub Push -> `/webhooks/github` -> Verify HMAC -> Extract commit metadata -> Call `bot.trigger_task` with a proactive prompt and reflection context.

## Integration Points
- **`panager.discord.bot`**: Consumer of OAuth completion and webhook triggers.
- **`panager.services`**: Used for OAuth token exchange and persistence (Google, GitHub, Notion).
- **`panager.db`**: Direct database access for token storage and user verification.
