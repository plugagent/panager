# Design: Scheduled Tool Execution via Agent Re-entry

## 1. 개요
현재 `panager`의 스케줄러는 단순 텍스트 알림 발송 기능만 제공합니다. 에이전트가 미래에 특정 도구를 실행하거나 복잡한 판단을 내릴 수 있도록 하기 위해, 스케줄러가 에이전트 워크플로를 다시 트리거하는 '에이전트 재진입(Agent Re-entry)' 구조를 도입합니다.

## 2. 주요 아키텍처 변경 사항

### 2.1 데이터 모델 확장 (`schedules` 테이블)
- `type`: `notification` (단순 DM), `command` (에이전트 실행) 컬럼 추가.
- `payload`: 실행할 명령 텍스트 또는 도구 실행에 필요한 JSON 데이터 저장.
- `metadata`: `depth` (무한 루프 방지용), `source` 등을 저장하는 JSONB 컬럼 추가.

### 2.2 동시성 제어 (Concurrency & Locking)
- `PanagerBot`에 사용자별 `asyncio.Lock`을 도입하여 동일 `thread_id`에 대한 Race Condition 방지.
- 스케줄러 트리거 시 락이 점유되어 있다면, 순차적으로 대기 후 실행.

### 2.3 보안 및 메시지 구분
- 사용자 입력과 시스템 트리거를 명확히 구분하기 위해 `AgentState`에 `is_system_trigger` 메타데이터 필드 추가.
- `[SCHEDULED_EVENT]`와 같은 내부 예약어를 통한 사용자의 권한 상승 시도(Spoofing) 차단 로직 구현.

## 3. 워크플로 상세

1. **예약 단계**:
   - 에이전트가 `schedule_create` 도구를 호출.
   - 이때 `type="command"`와 실행할 `command`를 전달.
2. **대기 단계**:
   - `APScheduler`가 PostgreSQL을 기반으로 대기.
3. **트리거 및 실행 단계**:
   - 스케줄러가 정해진 시간에 `PanagerBot.trigger_task` 호출.
   - 봇은 사용자별 락을 획득한 후, `is_system_trigger=True` 속성과 함께 에이전트 그래프 실행.
   - 에이전트는 해당 명령을 수행하고 결과를 사용자에게 스트리밍.

## 4. 고려 사항 및 방어 설계
- **무한 루프 방지**: 예약 작업 내에서 또 다른 예약을 생성할 때 `depth`를 체크하여 하드 리밋(예: depth=1) 적용.
- **상태 유효성 검증**: 에이전트가 실행 시점에 도구를 통해 현재 상태가 유효한지 먼저 확인하도록 프롬프트 가이드 제공.
- **비용 최적화**: 단순 알림은 LLM 호출 없이 기존 `notification` 타입으로 처리.

## 5. 단계별 구현 계획
1. `schedules` 테이블 마이그레이션 (Alembic).
2. `NotificationProvider` 인터페이스 확장 및 `PanagerBot` 구현.
3. 에이전트 상태(`AgentState`) 및 시스템 메시지 로직 수정.
4. 신규 도구 및 기존 스케줄 도구 고도화.
