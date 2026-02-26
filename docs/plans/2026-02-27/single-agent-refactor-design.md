# Design Doc: Single Agent & Strict Typing Refactor

## Overview
Refactor the multi-agent supervisor architecture into a single agent architecture. Implement strict typing for all agent state and node interactions, removing the use of `Any` and loosely defined dictionaries.

## Architecture Change
- **Before**: `discovery` -> `supervisor` -> (optional worker routing) -> `tool_executor` -> `supervisor`
- **After**: `discovery` -> `agent` -> `tool_executor` -> `agent`
- **Key differences**: 
    - `agent` directly calls tools and manages the conversation.
    - No multi-agent worker delegation (e.g., GoogleWorker, GithubWorker removed from graph).
    - Node names updated for clarity: `supervisor` -> `agent`.

## Strict Typing Implementation

### 1. Agent State
- `AgentState` (TypedDict) fields now use specific Pydantic models for structured data:
    - `discovered_tools`: `list[DiscoveredTool]`
    - `pending_reflections`: `list[PendingReflection]`
- Models defined:
    - `FunctionSchema`: OpenAI function call specification.
    - `DiscoveredTool`: Wrapper for tool search results.
    - `PendingReflection` & `CommitInfo`: Structured data for GitHub push events.

### 2. Node Outputs
- Each node in the graph now returns a specific `TypedDict`:
    - `discovery_node` -> `dict[str, list[DiscoveredTool]]`
    - `agent_node` -> `AgentNodeOutput`
    - `tool_executor_node` -> `ToolExecutorOutput`
    - `auth_interrupt_node` -> `AuthInterruptOutput`

## File Structure Changes
- `src/panager/agent/supervisor.py` -> `src/panager/agent/agent.py`
- `tests/agent/test_supervisor_routing.py` -> `tests/agent/test_agent_routing.py`

## Verification Results
- All 25 relevant tests passed.
- Strict typing confirmed via Pydantic model usage in nodes.
- Legacy multi-agent routing logic removed from the graph.
