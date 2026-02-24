# src/panager/agent/

## Responsibility
Core orchestration layer for the Panager agent. It defines the agent's cognition (LLM), memory (State), and capabilities (Tools) using LangGraph and LangChain.
- `state.py`: Defines the `AgentState` schema and message history reducers.
- `tools.py`: Implements per-user tool factories for Memory, Google Tasks/Calendar, and Scheduler.
- `workflow.py`: Orchestrates the `StateGraph` logic, node transitions, and message trimming.

## Design
- **State-Oriented (`state.py`)**: Uses `AgentState` (TypedDict) with LangGraph's `add_messages` reducer to manage conversation history. It tracks `user_id`, `username`, and persistent context like `timezone` and `memory_context`.
- **Closure-based Tool Factory (`tools.py`)**: Tools are constructed via factory functions (e.g., `make_memory_save`). This pattern injects `user_id` and service dependencies into the tool's execution scope at runtime, ensuring tools are bound to the specific user session.
- **Protocol-Driven**: Employs the `UserSessionProvider` protocol to decouple agent logic from the Discord-specific client, facilitating easier testing and alternative interfaces.
- **ReAct Pattern (`workflow.py`)**: Implements a standard cyclic workflow (Agent -> Tools -> Agent) using a `StateGraph`.

## Flow
1. **Entry**: Graph starts at the `agent` node via `START`.
2. **Cognition (`_agent_node`)**: 
   - **Contextualization**: Resolves timezone and formats current time with relative date markers (내일, 모레, etc.) to ground the LLM.
   - **Memory Injection**: Attaches relevant memory context retrieved from previous interactions.
   - **History Management**: Trims the message history using `trim_messages` (strategy="last") to maintain token efficiency based on `checkpoint_max_tokens`.
   - **System Trigger Handling**: If `is_system_trigger` is set, the prompt is adjusted to handle scheduled tasks/notifications.
   - **LLM Call**: Invokes the LLM with a system prompt and dynamically bound tools.
3. **Routing (`_should_continue`)**: A conditional edge that checks for `tool_calls` in the AI's response to decide whether to stop or execute actions.
4. **Action (`_tool_node`)**: 
   - **Parallel Execution**: Dispatches multiple tool calls concurrently using `asyncio.gather`.
   - **Auth Interception**: Specifically catches `GoogleAuthRequired` exceptions, preserves the user's original intent in `pending_messages`, and returns an OAuth URL.
5. **Loop**: Tool results are fed back into the `agent` node for final synthesis and response.

## Integration
- **Bot Handlers**: The compiled graph is consumed by `panager.discord.handlers` to process DM interactions.
- **Service Layer**:
  - `MemoryService`: Provides vector-based long-term memory.
  - `GoogleService`: Manages Google Calendar and Tasks integration with OAuth.
  - `SchedulerService`: Allows the agent to schedule future DM notifications or commands.
- **Checkpointing**: Integrated with `AsyncPostgresSaver` in the main entrypoint to persist state across bot restarts using `thread_id=user_id`.
