# src/panager/agent/

## Responsibility
Core orchestration layer implementing a **Supervisor-Worker multi-agent architecture**. It manages specialized sub-agents to handle diverse user requests across multiple integrations.
- `supervisor.py`: Central routing logic that decides the next specialized worker or task completion.
- `workflow.py`: Defines the global `StateGraph` and integrates worker sub-graphs.
- `state.py`: Shared state schema (`AgentState`) using LangGraph reducers.
- `google/`, `github/`, `notion/`, `memory/`, `scheduler/`: Domain-specific sub-agents (workers).

## Design Patterns
- **Supervisor Pattern**: A central LLM-based node (`supervisor_node`) manages task delegation and synthesis.
- **Hierarchical Graphs**: Each worker is a separate sub-graph, allowing for modular capability expansion.
- **State-Oriented**: Uses `AgentState` with `add_messages` to maintain conversation history and cross-worker context.
- **Interrupt/Resume Pattern**: Uses LangGraph `interrupt` for OAuth flows, allowing the agent to pause for user authentication and resume exactly where it left off.
- **Closure-based Tool Injection**: Service dependencies are injected into worker tools via factory functions, bound to specific `user_id` sessions.

## Data & Control Flow
1. **Routing (`supervisor_node`)**: Receives the user message, analyzes current state (including `task_summary` from previous workers), and selects the `next_worker` via the `Route` model.
2. **Specialist Execution**: The main graph routes control to the selected worker node (e.g., `GoogleWorker`).
3. **Internal Processing**: The worker sub-graph executes its logic, potentially calling multiple tools (Calendar, Tasks, etc.).
4. **Auth Interception**: If a worker raises an auth exception, the graph transitions to `auth_interrupt`, generating an OAuth URL and suspending execution.
5. **Synthesis**: Upon worker completion, control returns to the Supervisor with a `task_summary` for final synthesis or further delegation.
6. **Termination**: The Supervisor returns `FINISH` to end the graph execution and deliver the final response.

## Integration Points
- **Discord Handlers**: Consumes the compiled `StateGraph` to process real-time DM interactions.
- **Service Layer**: 
  - `GoogleService`, `GithubService`, `NotionService`: External API orchestrators.
  - `MemoryService`: Semantic search/storage for user context.
  - `SchedulerService`: Infrastructure for delayed notifications and re-entry commands.
- **Persistence**: Integrated with `AsyncPostgresSaver` for durable conversation checkpoints.
