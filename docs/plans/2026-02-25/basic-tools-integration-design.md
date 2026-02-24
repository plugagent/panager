# Design Document: Basic Tools Integration and Enforcement

## Purpose
Refactor the agent's toolset to improve reliability, reduce token usage, and enforce mandatory parameters for core actions. This is achieved by grouping tools into domains and removing optional/ambiguous parameters from the "Basic" toolset.

## Key Principles
1. **Domain Integration**: Consolidate individual tools into four domain-specific managers: `manage_user_memory`, `manage_dm_scheduler`, `manage_google_tasks`, and `manage_google_calendar`.
2. **Action-Based Dispatch**: Each tool uses an `action` enum to determine which sub-logic to execute.
3. **Strict Basic Tooling**: Parameters that were previously optional (e.g., task notes, event descriptions) are completely removed from these basic tools to focus on core functionality.
4. **Enforced Mandatory Fields**: While the integrated tool schema allows `None` for fields not used by a specific action, the tool will enforce (via validators) that required fields for the *current* action are present.

## Tool Specifications

### 1. `manage_user_memory`
- **Actions**: `save`, `search`
- **Parameters**:
    - `action` (Required): `save` | `search`
    - `text` (Required): Content to save or query string.

### 2. `manage_dm_scheduler`
- **Actions**: `create`, `cancel`
- **Parameters**:
    - `action` (Required): `create` | `cancel`
    - `text` (Required for `create`): Notification/Command content.
    - `trigger_at` (Required for `create`): ISO 8601 timestamp.
    - `schedule_id` (Required for `cancel`): ID of the schedule to cancel.

### 3. `manage_google_tasks`
- **Actions**: `list`, `create`, `update_status`, `delete`
- **Parameters**:
    - `action` (Required): `list` | `create` | `update_status` | `delete`
    - `task_id` (Required for `update_status`, `delete`): Target task ID.
    - `title` (Required for `create`): Task title.
    - `status` (Required for `update_status`): `completed` | `needsAction`.

### 4. `manage_google_calendar`
- **Actions**: `list`, `create`, `delete`
- **Parameters**:
    - `action` (Required): `list` | `create` | `delete`
    - `days_ahead` (Required for `list`): Number of days to look ahead (int).
    - `title` (Required for `create`): Event summary.
    - `start_at` (Required for `create`): ISO 8601 start time.
    - `end_at` (Required for `create`): ISO 8601 end time.
    - `event_id` (Required for `delete`): Target event ID.
    - `calendar_id` (Required for `delete`): Target calendar ID (usually 'primary').

## Technical Implementation
- **Schema**: Use Pydantic models with `@model_validator(mode="after")` to check action-specific requirements.
- **Error Handling**: Return a structured JSON error if mandatory fields for an action are missing, allowing the LLM to self-correct.
- **Workflow**: Update `_build_tools` in `workflow.py` to instantiate and bind these 4 tools.
