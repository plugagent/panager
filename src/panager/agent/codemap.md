# src/panager/agent/

## Responsibility
Core orchestration layer for the Panager agent. Defines the agentic workflow, state management, and tool integration using LangGraph and LangChain.

## Design
- **State-Oriented**: Uses `AgentState` (TypedDict) with LangGraph's `add_messages` reducer to manage conversation history and context.
- **Protocol-Driven**: Employs the `UserSessionProvider` protocol to decouple agent logic from the Discord-specific client.
- **Factory Pattern**: Tools are dynamically constructed via factory functions (`make_*`) in `tools.py`, injecting user-specific context and services.
- **Cyclic Workflow**: Implements a standard ReAct pattern (Agent -> Tools -> Agent) via `StateGraph`.

## Flow
1. **Entry**: Graph starts at the `agent` node via `START`.
2. **Cognition (`_agent_node`)**: 
   - Prepares context: Resolves timezone, formats current time, and retrieves memory context.
   - History Management: Trims messages based on `checkpoint_max_tokens`.
   - LLM Call: Invokes the LLM with a system prompt and bound tools.
3. **Routing (`_should_continue`)**: Checks for `tool_calls` in the LLM response.
4. **Action (`_tool_node`)**: 
   - Parallel Execution: Runs multiple tool calls concurrently using `asyncio.gather`.
   - Auth Handling: Catches `GoogleAuthRequired` to trigger the OAuth flow, saving the original request for later.
5. **Loop**: Tool results are fed back into the `agent` node until a final response is generated.

## Integration
- **Internal Consumers**: Bot handlers (e.g., `panager.bot.handlers`) that invoke the compiled graph.
- **Service Dependencies**: 
  - `MemoryService`: Long-term memory storage and retrieval.
  - `GoogleService`: Integration with Google Calendar and Tasks.
  - `SchedulerService`: Managing scheduled DM notifications.
- **External Dependencies**: 
  - LangGraph/LangChain: Workflow orchestration and LLM abstractions.
  - OpenAI/ChatOpenAI: LLM provider.
