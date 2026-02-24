# src/panager/discord/

Discord 봇 인터페이스 및 실시간 메시지 처리를 담당하는 모듈입니다.

## Responsibility

- **사용자 인터페이스 (Entry Point)**: Discord DM을 통해 사용자 입력을 수신하고, 에이전트의 사고 과정 및 결과를 실시간으로 출력합니다.
- **라이프사이클 관리**: Discord 클라이언트 연결 유지, 이벤트 루프 관리 및 백그라운드 태스크(OAuth 감시 등)를 실행합니다.
- **알림 및 트리거 허브**: 스케줄러에서 발생하는 알림을 사용자에게 전달하거나, 예약된 시간에 에이전트 작업을 자동으로 시작(trigger)합니다.
- **상태 정규화**: Discord 이벤트를 `AgentState` 구조로 변환하여 LangGraph 엔진에 전달합니다.

## Design

- **Inheritance Pattern**: `PanagerBot`은 `discord.Client`를 상속받아 DM 필터링 및 커스텀 이벤트 처리 로직을 확장합니다.
- **Concurrency Control**: `_user_locks` (`dict[int, asyncio.Lock]`)를 사용하여 사용자별로 요청을 직렬화 처리함으로써, 동일 사용자에 대한 상태 전이 경합(Race Condition)을 방지합니다.
- **Streaming UI Pattern**: `_stream_agent_response`에서 디바운싱(0.2s) 기반의 메시지 편집 루프를 구현하여, 속도 제한을 준수하면서도 실시간 응답을 제공합니다.
- **Provider Interface**: `NotificationProvider` 프로토콜을 구현하여 서비스 레이어(Scheduler)가 Discord 구현체에 직접 의존하지 않도록 분리합니다.
- **Resilient Messaging**: Discord의 2,000자 제한을 고려하여 긴 응답을 자동으로 여러 메시지로 분할 송신합니다.

## Flow

1. **입력 수신**:
   - **사용자 트리거**: `on_message` 발생 시 `handle_dm`이 DB에 사용자 정보를 등록(Upsert)하고 락을 획득합니다.
   - **시스템 트리거**: 스케줄러의 `trigger_task` 호출 또는 OAuth 인증 완료(`_process_auth_queue`) 시 에이전트 작업이 시작됩니다.
2. **에이전트 실행**:
   - `_stream_agent_response`가 `graph.astream(..., stream_mode="messages")`을 호출하여 추론 청크를 스트리밍합니다.
3. **실시간 렌더링**:
   - `AIMessageChunk`가 수신될 때마다 내용을 누적하고, 주기적으로 Discord 메시지를 `edit`하여 사용자에게 노출합니다.
   - 메시지 길이가 2,000자를 초과하면 새 메시지를 생성하여 스트리밍을 이어갑니다.
4. **완료 및 정리**:
   - 스트리밍 종료 후 최종 텍스트로 메시지를 확정하고, "생각하는 중..." 등의 임시 메시지를 삭제합니다.

## Integration

- **Core Agent**: `panager.agent.workflow`에서 생성된 컴파일된 그래프를 주입받아 실행합니다.
- **Services**: `SchedulerService`와 상호작용하여 알림을 발송하고, `GoogleService`의 OAuth 완료 이벤트를 `auth_complete_queue`를 통해 전달받습니다.
- **Database**: `panager.db`를 사용하여 사용자 가입 처리 및 세션 관리를 수행합니다.
- **External**: `discord.py` 라이브러리를 통해 Discord Gateway API와 통신합니다.
