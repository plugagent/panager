# src/panager/agent/github/

## Responsibility
GitHub 저장소 조회 및 Webhook 설정을 담당하는 전담 워커 에이전트입니다. 사용자의 리포지토리를 탐색하거나, 자동화된 워크플로우를 위한 웹훅 연동을 지원합니다.

## Design
- **Worker-Agent Pattern**: 독립적인 의사결정과 실행 루프를 가진 서브 그래프 구조입니다.
- **Tool Factory**: `make_github_tools`를 통해 서비스 의존성이 주입된 도구 세트를 동적으로 생성합니다.
- **Conditional Routing**: 도구 호출 여부 및 인증 필요 여부(`GithubAuthRequired`)에 따라 흐름을 제어합니다.

## Tool Signatures

### `list_github_repositories`
- **Input**: None (빈 `ListReposInput` 사용)
- **Output**: JSON string
    - `{"status": "success", "repositories": [{"full_name": "...", "description": "...", "html_url": "...", "updated_at": "..."}, ...]}`

### `setup_github_webhook`
- **Input**:
    - `repo_full_name` (str): 저장소 전체 이름 (예: 'owner/repo')
    - `webhook_url` (str): 페이로드를 수신할 서버 URL
- **Output**: JSON string
    - 성공: `{"status": "success", "message": "Webhook created successfully"}`
    - 실패: `{"status": "error", "message": "error_details"}`

## Data & Control Flow
1. **Input**: `WorkerState`를 통해 작업(`task`)과 이전 메시지 내역을 전달받습니다.
2. **Agent Node**: 시스템 프롬프트와 함께 LLM을 호출하여 수행할 작업을 결정합니다.
3. **Condition**: `_worker_should_continue`에서 도구 호출 필요성 또는 인증 URL 생성 여부를 확인합니다.
4. **Tool Node**: `GithubService`를 사용하여 실제 API 요청을 수행합니다. 인증 오류 시 `auth_request_url`을 상태에 저장하고 종료합니다.
5. **Output**: 최종 요약(`task_summary`) 또는 인증 요청 URL을 반환합니다.

## Integration Points
- **Dependencies**: `panager.services.github.GithubService` (GitHub API 연동)
- **State Management**: `panager.agent.state.WorkerState` 공유
- **Consumers**: 메인 에이전트 그래프(Orchestrator)에서 GitHub 관련 작업 발생 시 호출됩니다.
