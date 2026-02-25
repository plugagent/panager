# src/panager/agent/google/

## Responsibility
Google Calendar 및 Google Tasks 관리 전담 워커 에이전트입니다. 일정 조회/생성/삭제 및 할 일 목록 관리를 담당합니다.

## Design Patterns
- **Worker-Agent Pattern**: Agent node와 Tool node로 구성된 전담 서브 그래프입니다.
- **Factory Pattern**: `make_manage_google_calendar`, `make_manage_google_tasks`를 통해 도구를 생성합니다.
- **Input Validation**: Pydantic 모델(`CalendarToolInput`, `TaskToolInput`)을 사용하여 API 호출 전 인자의 유효성을 검증합니다.

## Data & Control Flow
1. **Input**: `WorkerState` (task, messages, user_id 등).
2. **LLM Reasoning**: 사용자 요청에 따라 Calendar 혹은 Tasks 도구 호출을 결정합니다.
3. **Execution**: `google_service`를 통해 Google API를 호출합니다. `asyncio.to_thread`를 사용하여 동기 Google 클라이언트 라이브러리를 비동기 환경에서 실행합니다.
4. **Error Handling**: `GoogleAuthRequired` 예외 발생 시 OAuth 인증 URL을 생성하여 흐름을 중단하고 사용자에게 전달합니다.
5. **Result**: 수행 결과를 JSON 형태로 반환하며, 최종 단계에서 `task_summary`를 작성합니다.

## Integration Points
- **Dependencies**: 
    - `panager.services.google.GoogleService` (핵심 서비스)
    - `panager.services.memory.MemoryService`
    - `panager.services.scheduler.SchedulerService`
- **Integration**: 메인 그래프의 노드로 통합되어 Google 관련 자연어 요청을 처리합니다.
