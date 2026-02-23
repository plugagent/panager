# Task 8: Final Cleanup and Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finalize the SOLID refactoring by removing legacy code, consolidating tools, and ensuring all tests pass with the new structure.

**Architecture:** 
1. Move tool factories to `src/panager/agent/tools.py`.
2. Update `workflow.py` to use the consolidated tools.
3. Remove legacy directories (`google/`, `memory/`, `scheduler/`, `bot/`).
4. Update tests to point to the new service-oriented architecture.

**Tech Stack:** Python, LangGraph, Pytest

---

### Task 1: Consolidate Tool Factories

**Files:**
- Create: `src/panager/agent/tools.py`
- Modify: `src/panager/agent/workflow.py`

**Step 1: Create `src/panager/agent/tools.py`**
Combine tools from `src/panager/memory/tool.py`, `src/panager/google/*/tool.py`, and `src/panager/scheduler/tool.py`.

**Step 2: Update `src/panager/agent/workflow.py`**
Update imports in `_build_tools` to use `panager.agent.tools`.

**Step 3: Verify workflow builds**
Run a simple test to check imports.

### Task 2: Remove Legacy Code

**Files:**
- Delete: `src/panager/memory/`
- Delete: `src/panager/google/`
- Delete: `src/panager/scheduler/`
- Delete: `src/panager/bot/`
- Delete: `src/panager/config.py`
- Delete: `src/panager/logging.py`
- Delete: `src/panager/agent/graph.py`

**Step 1: Remove directories**
```bash
rm -rf src/panager/memory src/panager/google src/panager/scheduler src/panager/bot
```

**Step 2: Remove legacy files in root**
```bash
rm src/panager/config.py src/panager/logging.py src/panager/agent/graph.py
```

### Task 3: Update Tests - Core and Config

**Files:**
- Modify: `tests/test_config.py`
- Modify: `tests/test_logging.py`
- Modify: `tests/test_db_connection.py`

**Step 1: Fix `tests/test_config.py`**
Ensure it handles `POSTGRES_PORT` correctly and imports from `panager.core.config`.

**Step 2: Fix `tests/test_logging.py`**
Import from `panager.core.logging`.

### Task 4: Update Tests - Agent and Workflow

**Files:**
- Rename: `tests/agent/test_graph.py` -> `tests/agent/test_workflow.py`
- Modify: `tests/agent/test_workflow.py`

**Step 1: Update imports in `test_workflow.py`**
Replace `panager.agent.graph` with `panager.agent.workflow`.

### Task 5: Update Tests - Tools

**Files:**
- Create: `tests/agent/test_tools.py` (combining old tool tests)
- Delete: `tests/memory/test_tool.py`, `tests/google/*/test_tool.py`, `tests/scheduler/test_tool.py`

**Step 1: Migrate tool tests**
Update tests to mock services correctly and test the tools in `panager.agent.tools`.

### Task 6: Final Verification

**Step 1: Run full test suite**
Run: `make test`
Expected: 100% PASS

**Step 2: Lint and Format**
Run: `uv run ruff check src/ && uv run ruff format src/`

**Step 3: Commit**
```bash
git add .
git commit -m "chore: remove legacy code and finalize refactoring"
```
