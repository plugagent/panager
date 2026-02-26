# SchedulerService Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement 100% coverage unit tests and enhanced integration tests for `SchedulerService`.

**Architecture:** 
- Unit tests will use heavy mocking of `asyncpg` and `apscheduler`.
- Integration tests will use a real test database and mocked `NotificationProvider` and `AsyncIOScheduler`.

**Tech Stack:** `pytest`, `pytest-asyncio`, `unittest.mock`, `asyncpg`.

---

### Task 1: Setup Unit Test File and Basic Mocking

**Files:**
- Create: `tests/services/test_scheduler.py`

**Step 1: Write the initial test file with fixtures**
Include fixtures for `mock_pool`, `mock_conn`, `mock_scheduler`, and `mock_provider`.

**Step 2: Commit**
`git add tests/services/test_scheduler.py && git commit -m "test: setup scheduler unit test file"`

---

### Task 2: Test SchedulerService Initialization and Provider Setup

**Files:**
- Modify: `tests/services/test_scheduler.py`

**Step 1: Write tests for `__init__` and `set_notification_provider`**
Verify `AsyncIOScheduler.start` is called and provider is updated.

**Step 2: Run tests**
`pytest tests/services/test_scheduler.py`

**Step 3: Commit**
`git commit -am "test: scheduler init and provider setup"`

---

### Task 3: Test add_schedule

**Files:**
- Modify: `tests/services/test_scheduler.py`

**Step 1: Write test for `add_schedule`**
Verify DB insertion with `fetchval` and `scheduler.add_job` call.

**Step 2: Run tests**
`pytest tests/services/test_scheduler.py`

**Step 3: Commit**
`git commit -am "test: scheduler add_schedule"`

---

### Task 4: Test cancel_schedule

**Files:**
- Modify: `tests/services/test_scheduler.py`

**Step 1: Write tests for `cancel_schedule`**
Cover success, failure (rows_affected=0), and scheduler exception cases.

**Step 2: Run tests**
`pytest tests/services/test_scheduler.py`

**Step 3: Commit**
`git commit -am "test: scheduler cancel_schedule"`

---

### Task 5: Test _execute_schedule (Basic Flow)

**Files:**
- Modify: `tests/services/test_scheduler.py`

**Step 1: Write tests for `_execute_schedule` success cases**
Cover `notification` and `command` types. Verify DB update (`sent=True`).

**Step 2: Run tests**
`pytest tests/services/test_scheduler.py`

**Step 3: Commit**
`git commit -am "test: scheduler execute_schedule basic flows"`

---

### Task 6: Test _execute_schedule (Retry Logic and Error Handling)

**Files:**
- Modify: `tests/services/test_scheduler.py`

**Step 1: Write tests for `_execute_schedule` error cases**
Cover:
- No notification provider.
- Retry logic: 1 fail then success.
- Max retries exceeded.
- Exponential backoff (mock `asyncio.sleep`).

**Step 2: Run tests and check coverage**
`pytest --cov=src/panager/services/scheduler.py tests/services/test_scheduler.py`

**Step 3: Commit**
`git commit -am "test: scheduler retry logic and error handling"`

---

### Task 7: Test restore_schedules

**Files:**
- Modify: `tests/services/test_scheduler.py`

**Step 1: Write test for `restore_schedules`**
Verify DB fetch and multiple `add_job` calls.

**Step 2: Run tests and verify 100% coverage**
`pytest --cov=src/panager/services/scheduler.py tests/services/test_scheduler.py`

**Step 3: Commit**
`git commit -am "test: scheduler restore_schedules and achieve 100% coverage"`

---

### Task 8: Enhance Integration Tests - restore_schedules

**Files:**
- Modify: `tests/integration/test_simulation.py`

**Step 1: Add `test_restore_schedules`**
Insert rows to DB, call `restore_schedules`, verify mock scheduler calls.

**Step 2: Run integration test**
`POSTGRES_HOST=localhost POSTGRES_PORT=5433 pytest tests/integration/test_simulation.py`

**Step 3: Commit**
`git commit -am "test: integration test for restore_schedules"`

---

### Task 9: Enhance Integration Tests - cancel_schedule

**Files:**
- Modify: `tests/integration/test_simulation.py`

**Step 1: Add `test_cancel_schedule_integration`**
Add schedule, cancel it, verify DB and mock scheduler.

**Step 2: Run integration test**
`POSTGRES_HOST=localhost POSTGRES_PORT=5433 pytest tests/integration/test_simulation.py`

**Step 3: Commit**
`git commit -am "test: integration test for cancel_schedule"`

---

### Task 10: Final Verification

**Step 1: Run all tests and check total coverage**
`make test` (if available) or `pytest --cov=src/panager/services/scheduler.py tests/`

**Step 2: Commit and finish**
`git commit -m "test: complete scheduler testing suite"`
