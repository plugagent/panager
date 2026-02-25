# src/panager/agent/notion/

## Responsibility
Notion 데이터베이스 관리 및 페이지 생성을 담당하는 전담 워커 에이전트입니다.

## Design Patterns
- **Worker-Agent Pattern**: 독립적인 의사결정(Agent)과 실행(Tool) 루프를 가진 서브 그래프입니다.
- **Reflection Pattern**: 도구 실행 결과에서 `pending_reflections`를 추출하여 상태에 반영하는 구조를 가집니다.
- **Factory Pattern**: `make_notion_tools`를 통해 서비스 주입형 도구를 생성합니다.

## Data & Control Flow
1. **Input**: Notion 작업 요청이 포함된 `WorkerState`.
2. **Discovery**: `search_notion` 도구를 사용하여 대상 `database_id`를 탐색할 수 있습니다.
3. **Action**: `create_notion_page`를 호출하여 구조화된 데이터를 Notion에 전송합니다.
4. **Auth Flow**: `NotionAuthRequired` 발생 시 `auth_request_url`을 통해 사용자의 연동을 유도합니다.
5. **State Sync**: 실행 결과 중 후속 작업이 필요한 경우 `pending_reflections`를 통해 상위 그래프로 정보를 전달합니다.

## Integration Points
- **Dependencies**: `panager.services.notion.NotionService`
- **Integration**: 사용자의 기록 관리, 데이터베이스 기반 업무 보조 시 활용됩니다.
