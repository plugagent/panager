# Design Document: LangGraph 리팩토링 (Supervisor & Interrupt)

## 1. 개요
현재 `panager`의 단일 ReAct 그래프 구조를 Supervisor 패턴으로 전환하여 모듈화와 확장성을 확보하고, LangGraph의 `interrupt` 기능을 도입하여 Google OAuth 인증 흐름을 결정론적으로 관리합니다.

## 2. 아키텍처

### 2.1 계층형 자율 Worker 구조
전체 시스템을 하나의 거대한 에이전트가 아닌, 관리자(Supervisor)와 분야별 전문가(Workers)의 협업 구조로 재설계합니다.

- **Supervisor (Main Router)**: 사용자의 의도를 분석하여 적절한 Worker에게 작업을 할당하고, 최종 결과를 취합하여 응답합니다.
- **Workers (Sub-graphs)**:
    - **GoogleWorker**: 캘린더 및 할 일 관리 담당. (도구: `manage_google_calendar`, `manage_google_tasks`)
    - **MemoryWorker**: 장기 기억 저장 및 검색 담당. (도구: `manage_user_memory`)
    - **SchedulerWorker**: 알림 예약 및 취소 담당. (도구: `manage_dm_scheduler`)

### 2.2 상태 관리 (State Management)
- **AgentState (Main)**:
    - `messages`: 전체 대화 기록.
    - `next_worker`: 다음으로 실행할 작업자 이름.
    - `auth_request_url`: 인증이 필요할 때의 URL 저장소.
- **WorkerState (Sub)**:
    - `messages`: Worker 내부의 ReAct 루프 메시지 (메인과 분리하여 토큰 절약).
    - `task`: 할당받은 구체적 임무.
    - `main_context`: 사용자 이름, 시간대 등 공유 컨텍스트.

## 3. 인증 처리 (Interrupt & Resume)

### 3.1 흐름 (Control Flow)
1. **감지**: GoogleWorker 도구 실행 중 `GoogleAuthRequired` 발생 시 `auth_request_url` 상태 업데이트.
2. **중단**: `auth_interrupt_node`에서 `interrupt()` 호출. 그래프 실행이 DB(checkpoint)에 저장된 채로 멈춤.
3. **알림**: Discord 봇이 멈춘 상태를 감지하고 사용자에게 인증 버튼 전송.
4. **재개**: 사용자가 인증 완료 시 FastAPI 콜백을 통해 `Command(resume="auth_success")` 주입.
5. **완료**: 그래프가 깨어나며 LLM이 '인증 완료' 문맥을 인지하고 실패했던 작업을 자동 재시도.

## 4. 기대 효과
- **확장성**: 새로운 기능을 추가할 때 새로운 Worker 그래프만 연결하면 됨.
- **안정성**: 인증 등 외부 개입 상황에서 상태 유실 없이 작업 재개 가능.
- **가독성**: 비대했던 `_agent_node` 프롬프트가 각 Worker로 분산되어 관리 용이.

## 5. 테스트 계획
- 각 Worker 서브 그래프 독립 테스트.
- `interrupt` 시점의 체크포인트 데이터 정합성 검증.
- `Command(resume)`를 통한 전체 흐름(End-to-End) 테스트.
