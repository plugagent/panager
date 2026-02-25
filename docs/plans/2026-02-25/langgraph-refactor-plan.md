# LangGraph Refactoring (Supervisor & Interrupt) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 단일 ReAct 그래프를 Supervisor 패턴과 `interrupt` 기반 인증 처리 구조로 리팩토링합니다.

**Architecture:** Supervisor가 작업을 분류하고 Google, Memory, Scheduler 전담 Worker 서브 그래프에게 위임합니다. Google 인증 필요 시 `interrupt`를 통해 그래프를 중단하고 재개합니다.

**Tech Stack:** Python 3.13, LangGraph 0.2+, Pydantic v2

---

### Task 1: State 및 TypedDict 정의 업데이트

**Files:**
- Modify: `src/panager/agent/state.py`

**Step 1: AgentState 필드 추가 및 WorkerState 정의**

```python
from typing import Annotated, TypedDict, NotRequired, Literal
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    user_id: int
    username: str
    messages: Annotated[list[AnyMessage], add_messages]
    memory_context: str
    is_system_trigger: NotRequired[bool]
    timezone: NotRequired[str]
    # New fields
    next_worker: NotRequired[str]
    auth_request_url: NotRequired[str | None]
    task_summary: NotRequired[str]

class WorkerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    task: str
    main_context: dict
    auth_request_url: NotRequired[str | None]
```

**Step 2: Commit**

```bash
git add src/panager/agent/state.py
git commit -m "refactor: AgentState 업데이트 및 WorkerState 정의"
```

---

### Task 2: Worker 서브 그래프 빌더 구현 (Google Worker)

**Files:**
- Modify: `src/panager/agent/workflow.py`

**Step 1: Google Worker 그래프 빌더 함수 추가**

```python
def build_google_worker(llm, tools):
    # ReAct 패턴의 서브 그래프 빌드 로직
    # ... (상세 구현 생략, 실제 구현 시 workflow.py에 추가)
    pass
```

**Step 2: Commit**

```bash
git add src/panager/agent/workflow.py
git commit -m "feat: Google Worker 서브 그래프 빌더 추가"
```

---

### Task 3: Supervisor 및 Auth Interrupt 노드 구현

**Files:**
- Modify: `src/panager/agent/workflow.py`

**Step 1: Supervisor 노드 구현**
- LLM을 사용하여 다음 Worker를 결정하거나 종료(FINISH)를 결정하는 로직.

**Step 2: Auth Interrupt 노드 구현**
- `auth_request_url`이 있을 때 `interrupt()`를 호출하는 로직.

**Step 3: Commit**

```bash
git add src/panager/agent/workflow.py
git commit -m "feat: Supervisor 및 Auth Interrupt 노드 구현"
```

---

### Task 4: 메인 그래프 조립 및 라우팅 설정

**Files:**
- Modify: `src/panager/agent/workflow.py`

**Step 1: build_graph 함수 리팩토링**
- 모든 노드를 등록하고 Supervisor 기반의 엣지 연결.

**Step 2: Commit**

```bash
git add src/panager/agent/workflow.py
git commit -m "refactor: Supervisor 패턴으로 메인 그래프 조립"
```

---

### Task 5: 검증 및 테스트

**Files:**
- Test: `tests/panager/agent/test_workflow.py`

**Step 1: 기존 테스트 실행 및 성공 확인**
`uv run pytest tests/panager/agent/test_workflow.py -v`

**Step 2: Commit**

```bash
git commit -m "test: 리팩토링된 그래프 검증 완료"
```
