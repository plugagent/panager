# src/panager/agent/scheduler/

## Responsibility
DM 알림 예약 및 백그라운드 작업 스케줄링을 관리하는 에이전트입니다.

## Design Patterns
- **Simplified Worker**: 현재는 단일 노드 형태의 Placeholder 그래프 구조를 가집니다.
- **Validation**: Pydantic `ScheduleToolInput`을 통해 ISO 8601 날짜 형식 및 필수 인자(`command`, `trigger_at`)를 엄격하게 검증합니다.
- **Factory Pattern**: `make_manage_dm_scheduler` 도구 생성기를 제공합니다.

## Data & Control Flow
1. **Input**: 예약할 시간, 내용 및 작업 유형(`notification`|`command`).
2. **Scheduling**: `manage_dm_scheduler` 도구가 `SchedulerService`를 호출하여 DB에 작업을 등록합니다.
3. **Cancellation**: `schedule_id`를 기반으로 기존 예약된 작업을 취소할 수 있습니다.
4. **Result**: 생성된 `schedule_id`와 예약 시간을 포함한 확인 메시지를 반환합니다.

## Integration Points
- **Dependencies**: `panager.services.scheduler.SchedulerService`
- **Integration**: 사용자가 나중에 알려달라고 요청하거나, 주기적인 작업(예: 리포트 생성)을 예약할 때 사용됩니다.
