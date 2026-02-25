# 디자인 문서: 에이전트 도메인 기반 리팩토링 (Approach B)

**날짜:** 2026-02-25
**상태:** 승인됨
**목표:** `workflow.py`와 `tools.py`에 집중된 로직을 도메인(Google, Memory, Scheduler) 패키지로 분리하여 응집도를 높이고 관리를 용이하게 한다.

## 1. 아키텍처 개요 (Domain-driven)

각 기능 단위를 독립적인 패키지로 구성하고, 메인 그래프는 이를 조립하는 오케스트레이터 역할을 수행한다.

### 디렉토리 구조
```text
src/panager/agent/
├── state.py            # [Common] 공통 상태 (AgentState, WorkerState)
├── utils.py            # [Common] 공통 유틸리티 (LLM, Trimming, Time)
├── supervisor.py       # [Common] 중앙 라우팅 로직 (supervisor_node)
├── google/             # [Domain] Google 패키지
│   ├── graph.py        # 워커 서브그래프
│   └── tools.py        # 도구 정의
├── memory/             # [Domain] Memory 패키지
│   ├── graph.py
│   └── tools.py
├── scheduler/          # [Domain] Scheduler 패키지
│   ├── graph.py
│   └── tools.py
└── workflow.py         # [Entrypoint] 메인 그래프 조립 (build_graph)
```

## 2. 컴포넌트 상세 설계

### 2.1. Common (Layer 0)
- **`state.py`**: 모든 도메인에서 참조하는 최하위 모듈. 타입 정의만 포함하여 순환 참조를 방지한다.
- **`utils.py`**: LLM 생성 및 메시지 관리 등 공통 비즈니스 로직 수용.
- **`supervisor.py`**: 도메인 간 이동을 결정하는 Supervisor 노드와 `Route` 모델 관리.

### 2.2. Domain Package (Layer 1)
- 각 도메인은 독립적으로 동작 가능한 `build_X_worker` 함수를 제공한다.
- 도메인 전용 도구는 해당 폴더의 `tools.py`에 위치시킨다.

### 2.3. Workflow (Layer 2)
- 각 도메인의 서브그래프를 가져와 전체 그래프를 조립한다.
- `auth_interrupt`와 같은 시스템 수준의 흐름 제어를 담당한다.

## 3. 이행 전략
- `state.py`, `utils.py`를 먼저 정비하여 기반을 다진다.
- 도메인을 하나씩 이전하며 로컬 테스트를 병행한다.
- 마지막에 `workflow.py`를 리팩토링하여 전체를 연결한다.
