# Design Doc: Tool Restructuring (`src/panager/tools/`)

## 1. Goal
Restructure the directory to group all tools in a single `src/panager/tools/` package. This aligns with the "Modular & Semantic Discovery Architecture" and prepares for 100+ tools by making them more discoverable and independent from the agent logic.

## 2. Problem Statement
Currently, tools are nested inside `src/panager/agent/<domain>/tools.py`. This structure is:
- **Coupled**: Tools are treated as internal to an agent worker, making cross-domain tasks feel less natural.
- **Inconsistent**: Some domains have more complex sub-agent graphs while others are just tools.
- **Hard to discover**: The registry has to search multiple deep subdirectories.

## 3. Proposed Structure
`src/panager/tools/`
  `__init__.py`: Central registry/discovery entry.
  `google.py`: Calendar & Tasks tools.
  `github.py`: Repository & Webhook tools.
  `notion.py`: Database & Page tools.
  `memory.py`: User context & memory tools.
  `scheduler.py`: Scheduling & Notification tools.

## 4. Migration Plan

### Step 1: File Relocation
1. `src/panager/agent/google/tools.py` -> `src/panager/tools/google.py`
2. `src/panager/agent/github/tools.py` -> `src/panager/tools/github.py`
3. `src/panager/agent/notion/tools.py` -> `src/panager/tools/notion.py`
4. `src/panager/agent/memory/tools.py` -> `src/panager/tools/memory.py`
5. `src/panager/agent/scheduler/tools.py` -> `src/panager/tools/scheduler.py`

### Step 2: Import Updates
- Update `src/panager/agent/registry.py` to import from the new `tools/` package.
- Update `src/panager/main.py` to import prototypes from the new locations.

### Step 3: Cleanup
- Remove empty `agent/<domain>/` directories (since graphs were already removed).

## 5. Success Criteria
- All tests in `tests/agent/test_new_architecture.py` and `tests/agent/test_workflow.py` pass.
- `uv run python -m panager.main --help` works without import errors.
