# Discord Bot and API Unit Tests Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement comprehensive unit tests for Discord bot logic, handlers, and API endpoints (auth, webhooks) with 90%+ coverage.

**Architecture:** Use `pytest` with `pytest-asyncio` and `unittest.mock.AsyncMock` to isolate components. Mock external dependencies like Discord API, Database, and internal services.

**Tech Stack:** `pytest`, `pytest-asyncio`, `fastapi.testclient`, `httpx`, `unittest.mock`.

---

### Task 1: Discord Bot Logic Tests

**Files:**
- Create: `tests/bot/test_bot_logic.py`
- Test: `tests/bot/test_bot_logic.py`

**Step 1: Write tests for PanagerBot logic**
- Test `_get_user_lock` (singleton-like behavior per user).
- Test `send_notification` (user fetch and DM send).
- Test `trigger_task` (agent state setup and streaming call).
- Test `_process_auth_queue` (resuming pending messages).
- Test `on_message` (filtering and routing).

**Step 2: Run tests and verify coverage**
Run: `uv run pytest tests/bot/test_bot_logic.py -v`

**Step 3: Commit**
```bash
git add tests/bot/test_bot_logic.py
git commit -m "test: add unit tests for PanagerBot logic"
```

### Task 2: Stream Handlers and DM Handler Tests

**Files:**
- Modify: `tests/bot/test_handlers.py` (Enhance existing tests)
- Test: `tests/bot/test_handlers.py`

**Step 1: Write/Enhance tests for handlers**
- Test `_stream_agent_response` with:
    - Incremental editing and cursor.
    - Debounce logic (using `time.monotonic` mocking if necessary).
    - Empty response fallback.
    - Cleanup of extra thinking messages.
- Test `handle_dm`:
    - Mock DB pool and connection.
    - Verify user insertion.
    - Verify call to `_stream_agent_response`.

**Step 2: Run tests and verify coverage**
Run: `uv run pytest tests/bot/test_handlers.py -v`

**Step 3: Commit**
```bash
git add tests/bot/test_handlers.py
git commit -m "test: enhance stream and DM handler tests"
```

### Task 3: API Auth Endpoints Tests

**Files:**
- Create: `tests/panager/api/test_auth_endpoints.py`
- Test: `tests/panager/api/test_auth_endpoints.py`

**Step 1: Write tests for auth endpoints**
- Mock `bot` in `app.state`.
- Test `/auth/google/login`, `/auth/github/login`, `/auth/notion/login`.
- Test `/auth/google/callback`, `/auth/github/callback`, `/auth/notion/callback`.
- Verify `exchange_code` calls and `auth_complete_queue` interaction.

**Step 2: Run tests and verify coverage**
Run: `uv run pytest tests/panager/api/test_auth_endpoints.py -v`

**Step 3: Commit**
```bash
git add tests/panager/api/test_auth_endpoints.py
git commit -m "test: add unit tests for API auth endpoints"
```

### Task 4: API Webhook Endpoints Tests

**Files:**
- Create: `tests/panager/api/test_webhook_endpoints.py`
- Test: `tests/panager/api/test_webhook_endpoints.py`

**Step 1: Write tests for webhooks**
- Test `verify_signature` (valid/invalid cases).
- Test `github_webhook` POST endpoint.
- Mock DB for user lookup.
- Verify `bot.trigger_task` is called.

**Step 2: Run tests and verify coverage**
Run: `uv run pytest tests/panager/api/test_webhook_endpoints.py -v`

**Step 3: Commit**
```bash
git add tests/panager/api/test_webhook_endpoints.py
git commit -m "test: add unit tests for API webhook endpoints"
```

### Task 5: Final Coverage Check

**Step 1: Run all tests with coverage report**
Run: `uv run pytest --cov=src/panager/discord --cov=src/panager/api tests/bot tests/panager/api`
Expected: 90%+ coverage for target modules.
