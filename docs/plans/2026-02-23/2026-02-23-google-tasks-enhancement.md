# Design: Google Tasks Enhancement

## 1. 개요
기존의 단순 제목 기반 할 일 추가 기능을 넘어, 메모(notes), 계층 구조(parent_id), 상세 수정 및 삭제 기능을 지원하도록 Google Tasks 도구 세트를 고도화합니다.

## 2. 도구별 주요 변경 사항

### 2.1 `task_create` (생성)
- **추가 필드**:
  - `notes`: 할 일에 대한 상세 설명.
  - `parent_id`: 상위 할 일 아래에 하위 할 일(subtask)로 생성하기 위한 부모 ID.
- **기능**: 단순히 제목만 넣던 방식에서 상세 속성을 포함한 생성이 가능해짐.

### 2.2 `task_update` (수정) - 신규
- **기능**: 기존 할 일의 제목, 메모, 완료 여부(status), 기한(due), 중요 표시(starred) 등을 개별적으로 수정.
- **특이 사항**: `starred` 필드는 Google Tasks 공식 문서상 직접적인 지원 여부가 불분명하나, 사용자 경험을 위해 실험적으로 필드 정의에 포함.

### 2.3 `task_delete` (삭제) - 신규
- **기능**: `task_id`를 기반으로 특정 할 일을 삭제.

### 2.4 `task_list` (조회)
- **변경**: 기존에는 "할 일이 없습니다" 등의 자연어 응답을 반환했으나, 에이전트의 데이터 활용도를 높이기 위해 전체 작업 아이템을 JSON 배열로 반환하도록 개선.

## 3. 구현 상세 (필드 및 타입)

### 3.1 `TaskCreateInput` (Pydantic Model)
- `title: str`
- `due_at: str | None`
- `notes: str | None`
- `parent_id: str | None`

### 3.2 `TaskUpdateInput` (Pydantic Model)
- `task_id: str`
- `title: str | None`
- `notes: str | None`
- `status: str | None` ('needsAction' or 'completed')
- `due_at: str | None`
- `starred: bool | None`

## 4. 관련 파일 및 경로
- 도구 정의: `src/panager/agent/tools.py`
- 워크플로 연동: `src/panager/agent/workflow.py`
- 테스트 코드: `tests/agent/test_tools.py`
