# src/panager/discord/

Discord bot interface implementing the primary communication channel and agent execution loop.

## Responsibility
- **UX Entry Point**: Handles DM reception, normalization, and response streaming.
- **Multi-Agent Execution**: Manages the lifecycle of LangGraph executions, including state persistence and lock management.
- **Auth Facilitation**: Captures OAuth interrupt signals and delivers interactive authorization buttons to users.
- **Proactive Triggering**: Handles system-initiated tasks (e.g., GitHub reflections, scheduled notifications).

## Design Patterns
- **Concurrency Control**: Per-user `asyncio.Lock` ensures serial execution of agent steps, preventing race conditions on shared conversation state.
- **Streaming UI**: Debounced message editing loop for real-time "thinking" and response rendering.
- **Provider Interface**: Implements `NotificationProvider` to decouple the scheduling logic from Discord-specific message delivery.
- **Interruption UI**: Converts LangGraph `interrupt` signals into user-friendly Discord components (buttons/URLs).

## Data & Control Flow
1. **Interaction**: User message -> `handle_dm` -> Acquire lock -> Load checkpoint -> `graph.astream`.
2. **Streaming**: Agent chunks are accumulated and periodically rendered via Discord `message.edit`.
3. **Interruption**: If `interrupt` (auth required), display OAuth button and halt.
4. **Resumption**: OAuth callback -> `auth_complete_queue` -> `_process_auth_queue` -> Resume graph with `auth_success`.
5. **System Trigger**: `trigger_task` -> Formulate system message -> Execute graph in background.

## Integration Points
- **`panager.agent.workflow`**: Executes the compiled multi-agent state machine.
- **`panager.services.scheduler`**: Consumes `SchedulerService` for notifications and re-entry.
- **`panager.api`**: Receives OAuth and webhook signals.

