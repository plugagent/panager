# Date/Time Intelligence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve agent's understanding of relative dates ("내일", "모레", "글피") and establish a default time of 09:00 AM when unspecified.

**Architecture:** Inject explicit date mappings into the system prompt and update tool field descriptions to guide the LLM's date/time parsing logic.

**Tech Stack:** Python, LangChain, Pydantic

---

### Task 1: Update `src/panager/agent/workflow.py`

**Files:**
- Modify: `src/panager/agent/workflow.py`

**Step 1: Calculate relative dates and update system prompt**

Add `timedelta` import and calculate the dates.

```python
from datetime import datetime, timedelta
# ...
    tomorrow = now + timedelta(days=1)
    day_after_tomorrow = now + timedelta(days=2)
    day_after_day_after_tomorrow = now + timedelta(days=3)
    
    relative_dates = (
        f"- 내일: {tomorrow.strftime('%Y-%m-%d')}\n"
        f"- 모레: {day_after_tomorrow.strftime('%Y-%m-%d')}\n"
        f"- 글피: {day_after_day_after_tomorrow.strftime('%Y-%m-%d')}"
    )
```

Inject into `system_prompt`.

**Step 2: Verify changes (Static Analysis)**

Run: `uv run ruff check src/panager/agent/workflow.py`

---

### Task 2: Update `src/panager/agent/tools.py`

**Files:**
- Modify: `src/panager/agent/tools.py`

**Step 1: Update Pydantic models with enhanced descriptions**

- `ScheduleCreateInput.trigger_at`
- `TaskCreateInput.due_at`
- `TaskUpdateInput.due_at`
- `EventCreateInput.start_at`
- `EventCreateInput.end_at`
- `EventUpdateInput.start_at`
- `EventUpdateInput.end_at`

Example for `due_at`:
`Field(..., description="ISO 8601 형식. 시간 미지정 시 오전 9시(09:00:00)를 기본값으로 사용하세요. 예: 2026-02-23T09:00:00+09:00")`

**Step 2: Verify changes (Static Analysis)**

Run: `uv run ruff check src/panager/agent/tools.py`

---

### Task 3: Verification & Commit

**Step 1: Run existing tests to ensure no regressions**

Run: `make test` (Note: requires DB, but logic changes might affect some tool tests)
Or run specific agent tests: `POSTGRES_HOST=localhost POSTGRES_PORT=5432 uv run pytest tests/panager/agent/ -v`

**Step 2: Final Git operations**

Run:
```bash
git add src/panager/agent/workflow.py src/panager/agent/tools.py
git commit -m "fix: 내일/모레/글피 이해 및 시간 미지정 시 오전 9시 기본값 적용 로직 추가"
```
