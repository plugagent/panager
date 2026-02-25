# src/panager/agent/github/

## Responsibility
GitHub 전담 워커 에이전트로, 사용자의 GitHub 저장소 목록 조회 및 Webhook 설정을 담당합니다.

## Design Patterns
- **Worker-Agent Pattern**: 전담 작업을 수행하는 독립적인 LangGraph 서브 그래프 구조를 가집니다.
- **Tool Factory**: `make_github_tools`를 통해 서비스 의존성이 주입된 도구 세트를 동적으로 생성합니다.
- **Conditional Routing**: 도구 호출 여부 및 인증 필요 여부(`GithubAuthRequired`)에 따라 흐름을 제어합니다.

## Data & Control Flow
1. **Input**: `WorkerState`를 통해 작업(`task`)과 이전 메시지 내역을 전달받습니다.
2. **Agent Node**: `_worker_agent_node`에서 시스템 프롬프트와 함께 LLM을 호출하여 수행할 작업을 결정합니다.
3. **Condition**: `_worker_should_continue`에서 도구 호출이 필요한지, 혹은 인증 URL이 생성되었는지 확인합니다.
4. **Tool Node**: `_worker_tool_node`에서 `GithubService`를 사용하여 실제 API 요청을 수행합니다. 인증 오류 시 `auth_request_url`을 상태에 저장하고 종료합니다.
5. **Output**: 최종 요약(`task_summary`) 또는 인증 요청 URL을 반환합니다.

## Integration Points
- **Dependencies**: `panager.services.github.GithubService` (GitHub API 연동)
- **State Management**: `panager.agent.state.WorkerState` 공유
- **Consumers**: 메인 에이전트 그래프(Orchestrator)에서 특정 GitHub 관련 작업 발생 시 호출됩니다.
