# Design: Tool Consolidation for Panager Agent

## Overview
Consolidate 12 fragmented tools in `src/panager/agent/tools.py` into 4 service-centric tools using Pydantic's Discriminated Union to improve reasoning accuracy, reduce context overhead, and simplify the agent's decision-making process.

## Goals
- Reduce tool count from 12 to 4.
- Use Discriminated Union to enforce action-specific schemas.
- Maintain existing functionality with service-centric naming.
- Improve response consistency.

## Design

### 1. Service-Centric Naming & Structure
Tools will be renamed to follow a `<service>_service` pattern:
- `google_tasks_service`
- `google_calendar_service`
- `internal_memory_service`
- `internal_scheduler_service`

### 2. Action Schemas (Discriminated Union)
Each service tool will accept a `Union` of Pydantic models, discriminated by an `action` field.

#### Google Tasks Service
- **Action**: `list`, `create`, `update`, `delete`
- **Schema**:
  - `list`: No additional params.
  - `create`: `title` (required), `due_at`, `notes`, `parent_id`.
  - `update`: `task_id` (required), `title`, `notes`, `status`, `due_at`, `starred`.
  - `delete`: `task_id` (required).

#### Google Calendar Service
- **Action**: `list`, `create`, `update`, `delete`
- **Schema**:
  - `list`: `days_ahead` (default 7).
  - `create`: `title`, `start_at`, `end_at` (required), `calendar_id`, `description`.
  - `update`: `event_id`, `calendar_id` (required), `title`, `start_at`, `end_at`, `description`.
  - `delete`: `event_id`, `calendar_id` (required).

#### Internal Memory Service
- **Action**: `save`, `search`
- **Schema**:
  - `save`: `content` (required).
  - `search`: `query` (required), `limit` (default 5).

#### Internal Scheduler Service
- **Action**: `create`, `cancel`
- **Schema**:
  - `create`: `command`, `trigger_at` (required), `type`, `payload`.
  - `cancel`: `schedule_id` (required).

### 3. Response Format
Unified JSON response:
```json
{
  "status": "success" | "error",
  "data": { ... },
  "message": "Optional error message"
}
```

## Implementation Strategy
1. Define unified Pydantic models for each service in `src/panager/agent/tools.py`.
2. Implement factory functions (`make_..._service`) that handle internal routing based on `action`.
3. Update `workflow.py` to use the new consolidated tools.
4. Verify via tests.
