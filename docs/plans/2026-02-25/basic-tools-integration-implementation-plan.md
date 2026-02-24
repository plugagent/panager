# Basic Tools Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 리액트(ReAct) 루프 효율을 높이기 위해 도구를 도메인별로 통합하고, 기본 도구에서 불필요한 옵션을 제거하며 필수 입력을 강제합니다.

**Architecture:** 도구를 `user_memory`, `dm_scheduler`, `google_tasks`, `google_calendar` 4개로 통합합니다. 각 도구는 `action` Enum을 통해 분기하며, Pydantic의 `@model_validator`를 사용하여 각 액션에 필요한 필드가 누락되지 않았는지 검증합니다.

**Tech Stack:** Python 3.13, Pydantic v2, LangChain, LangGraph

---

### Task 1: 도메인별 Action Enum 및 기본 모델 정의

**Files:**
- Modify: `src/panager/agent/tools.py`

**Step 1: Enum 정의**
`MemoryAction`, `ScheduleAction`, `TaskAction`, `CalendarAction`을 정의합니다.

**Step 2: Commit**
```bash
git add src/panager/agent/tools.py
git commit -m "refactor: 도메인별 Action Enum 정의"
```

---

### Task 2: `manage_user_memory` 통합 및 검증 로직 구현

**Files:**
- Modify: `src/panager/agent/tools.py`
- Test: `tests/agent/test_tools.py`

**Step 1: 통합 모델 및 팩토리 구현**
`save`, `search` 액션을 처리하는 `manage_user_memory` 도구를 구현합니다. `text` 필드는 항상 필수입니다.

**Step 2: 테스트 및 커밋**
```bash
uv run pytest tests/agent/test_tools.py
git commit -m "feat: manage_user_memory 통합 도구 구현"
```

---

### Task 3: `manage_dm_scheduler` 통합 및 검증 로직 구현

**Files:**
- Modify: `src/panager/agent/tools.py`

**Step 1: 통합 모델 구현**
`create` 시 `text`, `trigger_at` 필수, `cancel` 시 `schedule_id` 필수인 검증 로직을 포함합니다.

**Step 2: 커밋**
```bash
git commit -m "feat: manage_dm_scheduler 통합 도구 구현"
```

---

### Task 4: `manage_google_tasks` 통합 (Basic 스펙 적용)

**Files:**
- Modify: `src/panager/agent/tools.py`

**Step 1: 슬림화된 모델 구현**
`notes`, `due_at` 등 비어있어도 되는 필드를 제거하고 `list`, `create`, `update_status`, `delete` 액션을 통합합니다.

**Step 2: 커밋**
```bash
git commit -m "feat: manage_google_tasks 통합 도구 구현 (Basic)"
```

---

### Task 5: `manage_google_calendar` 통합 (Basic 스펙 적용)

**Files:**
- Modify: `src/panager/agent/tools.py`

**Step 1: 슬림화된 모델 구현**
`description`, `calendar_id`(생성 시) 등을 제거하고 `list`, `create`, `delete` 액션을 통합합니다.

**Step 2: 커밋**
```bash
git commit -m "feat: manage_google_calendar 통합 도구 구현 (Basic)"
```

---

### Task 6: 워크플로우 반영 및 시스템 프롬프트 업데이트

**Files:**
- Modify: `src/panager/agent/workflow.py`

**Step 1: 도구 바인딩 수정**
`_build_tools`에서 기존 12개 도구 대신 통합된 4개 도구만 반환하도록 수정합니다.

**Step 2: 시스템 프롬프트 수정**
"모든 리소스 관리는 도메인별 매니저 도구의 `action` 파라미터를 통해 수행된다"는 내용을 시스템 프롬프트에 명확히 기재합니다.

**Step 3: 커밋**
```bash
git commit -m "refactor: 워크플로우에 통합 도구 적용 및 프롬프트 업데이트"
```

---

### Task 7: 전체 테스트 및 정합성 검증

**Files:**
- Modify: `tests/agent/test_tools.py`, `tests/agent/test_workflow.py`

**Step 1: 테스트 코드 리팩토링**
변경된 도구 호출 방식에 맞춰 기존 테스트 코드를 수정합니다.

**Step 2: 전체 테스트 실행**
```bash
uv run pytest tests/agent/
```
