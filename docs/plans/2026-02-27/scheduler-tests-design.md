# SchedulerService Testing Design

## Overview
Implement comprehensive unit tests and enhance integration tests for `SchedulerService`.

## Unit Tests (tests/services/test_scheduler.py)
- **Target:** 100% coverage of `src/panager/services/scheduler.py`.
- **Mocks:**
    - `asyncpg.Pool`: Mock `acquire` and the connection's `fetchval`, `execute`, `fetch`.
    - `apscheduler.schedulers.asyncio.AsyncIOScheduler`: Mock `start`, `add_job`, `remove_job`.
    - `NotificationProvider`: Mock `send_notification`, `trigger_task`.
- **Test Cases:**
    - `__init__`: Verify scheduler starts.
    - `set_notification_provider`: Verify provider is set.
    - `add_schedule`: Verify DB insertion and `add_job` call.
    - `cancel_schedule`:
        - Success: Verify DB deletion and `remove_job`.
        - Job not found in scheduler: Verify it still returns `True` (handled by `except Exception`).
        - DB deletion failed: Verify returns `False`.
    - `_execute_schedule`:
        - `notification` type: Verify `send_notification` and DB update.
        - `command` type: Verify `trigger_task` and DB update.
        - No provider: Verify error log and early return.
        - Retry logic:
            - Fail 1st attempt, succeed 2nd attempt (using `side_effect`).
            - Fail all 3 attempts, verify error log.
            - Verify exponential backoff (`asyncio.sleep` called with `2**retry`).
    - `restore_schedules`: Verify DB fetch and `add_job` for each row.

## Integration Tests (tests/integration/test_simulation.py)
- **Target:** Verify DB interactions and end-to-end flow.
- **Test Cases:**
    - `test_restore_schedules`:
        - Setup: Insert 2 pending future schedules and 1 past/sent schedule.
        - Action: Call `restore_schedules`.
        - Verification: Verify `add_job` called 2 times with correct data.
    - `test_cancel_schedule`:
        - Setup: Add a schedule via `add_schedule`.
        - Action: Call `cancel_schedule`.
        - Verification: Verify row deleted from DB and `remove_job` called.

## Tech Stack
- `pytest`, `pytest-asyncio`
- `unittest.mock` (MagicMock, AsyncMock, patch)
- `asyncpg` (for integration tests)
