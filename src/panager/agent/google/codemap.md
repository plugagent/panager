# src/panager/agent/google/

## Responsibility
Google Calendar 및 Google Tasks 관리를 위한 전담 워커 에이전트를 정의합니다. 사용자의 일정을 조회/생성/삭제하거나 할 일을 관리하는 인터페이스를 제공합니다.

## Design
- **Worker-Agent Pattern**: Agent node와 Tool node로 구성된 전담 서브 그래프입니다.
- **Factory Pattern**: `make_manage_google_tasks`, `make_manage_google_calendar`를 통해 `user_id`와 `GoogleService`가 주입된 도구를 동적으로 생성합니다.
- **Input Validation**: Pydantic 모델(`CalendarToolInput`, `TaskToolInput`)을 사용하여 API 호출 전 인자의 유효성을 검증합니다.

## Tool Signatures

### `manage_google_tasks`
- **Input**:
    - `action` (Enum: `list`, `create`, `update_status`, `delete`): 수행할 작업
    - `task_id` (str, optional): 할 일 ID (`update_status`, `delete` 시 필수)
    - `title` (str, optional): 할 일 제목 (`create` 시 필수)
    - `status` (str, optional): 할 일 상태 (`update_status` 시 필수, 'needsAction' 또는 'completed')
- **Output**: JSON string
    - `list`: `{"status": "success", "tasks": [...]}`
    - `create`/`update_status`: `{"status": "success", "task": {...}}`
    - `delete`: `{"status": "success", "task_id": "..."}`

### `manage_google_calendar`
- **Input**:
    - `action` (Enum: `list`, `create`, `delete`): 수행할 작업
    - `event_id` (str, optional): 이벤트 ID (`delete` 시 필수)
    - `calendar_id` (str): 캘린더 ID (default: "primary")
    - `title` (str, optional): 이벤트 제목 (`create` 시 필수)
    - `start_at` (str, optional): ISO 8601 시작 시간 (`create` 시 필수)
    - `end_at` (str, optional): ISO 8601 종료 시간 (`create` 시 필수)
    - `days_ahead` (int): 조회 범위 일수 (default: 7)
- **Output**: JSON string
    - `list`: `{"status": "success", "events": [...]}`
    - `create`: `{"status": "success", "event": {...}}`
    - `delete`: `{"status": "success", "event_id": "..."}`

## Data & Control Flow
1. **Agent Node**: `llm.bind_tools`를 사용하여 도구를 바인딩하고, 사용자 요청에 따라 도구 호출 여부를 결정합니다.
2. **Tools Node**: `last_message.tool_calls`를 순회하며 실제 도구를 실행합니다. `GoogleAuthRequired` 예외 발생 시 OAuth 인증 URL을 생성하여 흐름을 중단합니다.
3. **Execution**: `asyncio.to_thread`를 사용하여 동기 Google 클라이언트 라이브러리를 비동기 환경에서 실행합니다.
4. **Summary**: 도구 호출이 없는 경우 작업 결과를 요약하여 `task_summary`에 저장합니다.

## Integration Points
- **Dependencies**: 
    - `panager.services.google.GoogleService` (핵심 서비스)
    - `panager.services.memory.MemoryService`
    - `panager.services.scheduler.SchedulerService`
- **Integration**: Supervisor(`supervisor_node`)에서 Google 관련 요청 발생 시 라우팅되어 실행됩니다.
