# src/panager/discord/

Discord 봇 인터페이스 및 실시간 메시지 처리를 담당하는 모듈입니다.

## Responsibility

- **사용자 인터페이스**: Discord DM을 통한 사용자 입력 수신 및 에이전트 응답 출력.
- **라이프사이클 관리**: Discord 클라이언트 연결 유지 및 서비스 초기화.
- **알림 허브**: 시스템 내부 서비스(스케줄러 등)에서 발생하는 알림을 Discord로 전달.
- **인증 가교**: OAuth 인증 완료 이벤트를 수신하여 중단되었던 에이전트 작업을 재개.

## Design

- **Asynchronous Event Handling**: `discord.Client`를 상속받아 비동기 이벤트 루프 기반으로 동작.
- **Separation of Concerns**: UI 로직(`bot.py`)과 메시지 처리 로직(`handlers.py`)을 분리.
- **Streaming UI**: 사용자 경험 개선을 위해 에이전트의 응답을 실시간으로 편집(`edit`)하며 노출하는 스트리밍 패턴 적용.
- **Resilient Message Processing**: 메시지 길이 제한(2000자) 자동 분할 처리 및 스트리밍 디바운싱(Debounce).

## Flow

1. **Input**: Discord 서버로부터 `on_message` 이벤트 발생 -> `handle_dm`으로 위임.
2. **Contextualization**: DB에서 사용자 정보를 확인/등록하고, LangGraph 실행을 위한 `state` 및 `config` 구성.
3. **Execution**: LangGraph `graph.astream`을 통해 추론 청크를 실시간으로 수신.
4. **Output**: `_stream_agent_response`가 청크를 조합하여 Discord 메시지를 생성 및 주기적으로 업데이트.
5. **Recovery**: 인증 필요 시 작업을 `pending_messages`에 보관 후, 인증 완료 시 `_process_auth_queue`가 감지하여 재실행.

## Integration

- **External**: `discord.py`를 통한 Discord Gateway API 연동.
- **Core Agent**: `panager.agent`에서 빌드된 LangGraph 객체를 주입받아 사용.
- **Services**: `MemoryService`, `GoogleService`, `SchedulerService`와 상호작용 (알림 제공자 역할 수행).
- **Persistence**: `panager.db`를 통해 사용자 정보를 데이터베이스에 저장.
