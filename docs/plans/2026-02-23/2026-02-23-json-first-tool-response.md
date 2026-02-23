# Design: JSON-First Tool Response Standard

## 1. 개요
에이전트가 도구의 실행 결과를 더 정확하게 파악하고, 사용자에게 응답을 생성할 때 원시 데이터를 활용할 수 있도록 모든 도구의 응답 형식을 JSON으로 표준화합니다.

## 2. 설계 원칙

### 2.1 자연어 응답 지양
- 기존: `"할 일이 추가되었습니다: [제목]"` (문자열)
- 변경: `{"status": "success", "task": {"id": "...", "title": "..."}}` (JSON)

### 2.2 표준 응답 필드
- `status`: 실행 결과 상태 (`success`, `failed`, `error`).
- `results` / `items` / `task` / `event`: 실행 결과에 따른 실제 데이터 객체 또는 배열.
- `message`: 오류 발생 시 상세 사유 설명.

### 2.3 프롬프트 최적화
- 시스템 프롬프트에 모든 도구 응답이 JSON으로 제공됨을 명시하여 에이전트가 `json.loads` 없이도 구조를 이해하도록 유도.
- 성공적인 결과(`status: success`)에 대해서는 중복 확인 없이 간결하게 사용자에게 전달하도록 가이드.

## 3. 주요 변경 사항 및 파일 경로

### 3.1 `src/panager/agent/tools.py`
- 모든 도구 함수(`memory_save`, `memory_search`, `task_list`, `event_list` 등)의 반환값을 `json.dumps(..., ensure_ascii=False)`로 래핑.
- `typing.Any` 및 `json` 모듈 임포트 추가.

### 3.2 `src/panager/agent/workflow.py`
- `_agent_node`의 `system_prompt`에 JSON 응답 관련 안내 문구 추가.
  > "참고: 모든 도구의 실행 결과는 JSON 데이터 구조로 제공됩니다. 결과가 성공적(status: success)이라면 불필요한 재질문 없이 사용자에게 간결하게 보고하세요."

## 4. 기대 효과
- **추론 정확도 향상**: 에이전트가 도구 응답 문자열에서 정보를 파싱하는 과정에서의 오류 감소.
- **스트리밍 품질 개선**: 구조화된 데이터를 바탕으로 에이전트가 더 명확한 요약 응답을 생성 가능.
- **확장성**: 추후 도구 응답에 더 복잡한 메타데이터를 추가하더라도 하위 호환성 유지 용이.
