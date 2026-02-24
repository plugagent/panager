# 설계 문서: 순환적 병렬 멀티 에이전트 시스템 (Cyclic Parallel Multi-Agent System)

## 1. 개요 (Purpose)
Panager의 도구 세트가 확장됨에 따라 단일 에이전트의 추론 부담을 줄이고, 독립적인 작업(일정 관리, 메모 저장 등)을 병렬로 처리하여 응답 속도와 정확도를 향상시키기 위한 아키텍처 전환입니다.

## 2. 아키텍처 설계 (Architecture)

### 2.1 제어 흐름 (Control Flow)
시스템은 **관리자(Supervisor)**와 **도메인 전문가(Worker)**들로 구성된 순환형 그래프 구조를 가집니다.

1.  **의도 파악 단계 (Intent Phase):** `Supervisor`가 사용자 메시지를 분석하여 필요한 전문가 목록(`selected_workers`)을 결정합니다.
2.  **병렬 실행 (Fan-out):** `Supervisor`가 결정한 전문가들을 `langgraph.types.Send`를 사용하여 동시에 호출합니다.
3.  **결과 수렴 (Fan-in/Join):** 모든 전문가가 작업을 마치면 LangGraph 엔진이 자동으로 동기화하여 `Supervisor`를 다시 호출합니다.
4.  **결과 요약 단계 (Synthesis Phase):** `Supervisor`가 전문가들의 보고를 취합하여 사용자에게 최종 응답을 제공합니다.

### 2.2 노드 정의 (Nodes)
- **`supervisor`**: 의도 분석 및 결과 요약을 담당하는 중앙 노드. `phase` 상태에 따라 행동이 결정됨.
- **`google_worker`**: Google Calendar 및 Tasks 도구를 사용하는 전문가.
- **`memory_worker`**: Memory (pgvector) 도구를 사용하는 전문가.
- **`scheduler_worker`**: 알림 및 예약 도구를 사용하는 전문가.

## 3. 데이터 설계 (Data Design)

### 3.1 상태 스키마 (AgentState)
```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    phase: Literal["intent", "synthesis"]
    selected_workers: list[str]
    loop_count: int
    timezone: str
    username: str
    user_id: int
```

### 3.2 리듀서 (Reducers)
- `messages` 필드는 `add_messages` 리듀서를 사용하여 병렬 전문가들의 응답을 순차적으로 축적합니다.

## 4. 핵심 메커니즘 (Key Mechanisms)

### 4.1 병렬 수렴 (Convergence)
LangGraph의 `Send` 객체와 조건부 에지를 활용합니다. 전문가 노드에서 `supervisor`로 향하는 에지는 모든 병렬 분기가 도착할 때까지 대기하도록 엔진에 의해 관리됩니다.

### 4.2 상태 단계 관리 (Phase Gating)
`phase` 필드를 통해 `Supervisor`의 역할을 엄격히 구분합니다.
- `intent`: 사용자의 입력을 분석하고 작업을 할당.
- `synthesis`: 전문가의 결과를 읽고 자연어로 요약.

## 5. 예외 처리 (Error Handling)
- **Circuit Breaker:** `loop_count`가 3회 이상일 경우 강제로 종료하여 무한 루프를 방지합니다.
- **Partial Failure:** 한 전문가가 실패하더라도 다른 전문가의 결과는 유지하며, `Supervisor`가 실패 원인을 포함하여 응답합니다.

## 6. 기대 효과 (Expected Impact)
- **성능:** I/O 집약적인 API 호출(Google)과 DB 검색(Memory)이 병렬로 처리되어 전체 레이턴시 단축.
- **정확도:** 각 에이전트가 소수의 도구(3~5개)만 보유하므로 도구 선택 오작동 최소화.
- **유지보수:** 새로운 도메인(예: 이메일, 웹 검색) 추가 시 기존 로직 수정 없이 노드만 추가 가능.
