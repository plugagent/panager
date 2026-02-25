# src/panager/agent/memory/

## Responsibility
사용자의 장기 메모리(Long-term Memory)를 관리하는 에이전트입니다. 중요한 정보를 저장하거나 과거의 대화/정보를 검색합니다.

## Design Patterns
- **Simplified Worker**: 현재는 단일 노드 형태의 Placeholder 그래프 구조를 가지고 있으나, 도구 로직은 완성되어 있습니다.
- **Vector Search Integration**: `MemoryService`를 통한 시맨틱 검색 기능을 도구로 캡슐화합니다.
- **Factory Pattern**: `make_manage_user_memory`를 통해 도구를 생성합니다.

## Data & Control Flow
1. **Input**: `WorkerState` 내의 검색 쿼리 또는 저장할 내용.
2. **Tool Invocation**: `manage_user_memory` 도구가 실행되어 `action`(`save`|`search`)에 따라 분기합니다.
3. **Service Layer**: `MemoryService`를 호출하여 PostgreSQL(pgvector)에 데이터를 저장하거나 유사도 검색을 수행합니다.
4. **Output**: 저장 성공 여부 또는 검색된 결과 리스트를 JSON 형태로 반환합니다.

## Integration Points
- **Dependencies**: `panager.services.memory.MemoryService` (Vector DB 연동)
- **Integration**: 에이전트가 사용자의 과거 맥락을 파악해야 하거나, 새로운 지식을 습득해야 할 때 호출됩니다.
