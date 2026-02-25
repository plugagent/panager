# Repository Atlas: Panager

## Project Responsibility
Panager는 Discord DM에서 동작하는 개인 비서 에이전트 봇입니다. Google Calendar/Tasks, GitHub, Notion 등 다양한 도구를 통합하여 사용자의 일정을 관리하고, 업무 기록 및 개인화된 메모리(Semantic Search) 기능을 제공합니다. LangGraph를 이용한 계층적 멀티 에이전트(Supervisor-Worker) 아키텍처를 채택하여 복잡한 요청을 효율적으로 분배하고 처리합니다.

## System Entry Points & Root Assets
- `src/panager/main.py`: 애플리케이션 진입점. 모든 서비스 초기화 및 봇/API 서버 실행.
- `AGENTS.md`: 개발자 및 에이전트를 위한 가이드. 아키텍처, 코딩 표준, 운영 명령 포함.
- `pyproject.toml`: 의존성 관리 파일 (`uv` 사용).
- `Makefile`: 개발 라이프사이클(DB 설정, 마이그레이션, 테스트 등) 표준 명령어.
- `Dockerfile`: 프로덕션 배포용 멀티 스테이지 빌드 스크립트.

## Directory Map (Aggregated)
| Directory | Responsibility Summary | Detailed Map |
|-----------|------------------------|--------------|
| `src/panager/agent/` | **Multi-Agent Orchestrator**: Supervisor 패턴을 통한 작업 분배 및 관리. | [View Map](src/panager/agent/codemap.md) |
| `src/panager/agent/google/` | **Google Worker**: Calendar/Tasks 통합 관리 및 OAuth 생명주기 처리. | [View Map](src/panager/agent/google/codemap.md) |
| `src/panager/agent/github/` | **GitHub Worker**: 저장소 조회 및 웹훅 기반 자동화 지원. | [View Map](src/panager/agent/github/codemap.md) |
| `src/panager/agent/notion/` | **Notion Worker**: 구조화된 데이터 기록 및 페이지 관리. | [View Map](src/panager/agent/notion/codemap.md) |
| `src/panager/agent/memory/` | **Memory Worker**: 사용자별 시맨틱 저장 및 검색 기능 제공. | [View Map](src/panager/agent/memory/codemap.md) |
| `src/panager/agent/scheduler/` | **Scheduler Worker**: 알림 예약 및 백그라운드 작업 실행. | [View Map](src/panager/agent/scheduler/codemap.md) |
| `src/panager/api/` | **API Server**: OAuth 콜백 및 GitHub 웹훅 처리. | [View Map](src/panager/api/codemap.md) |
| `src/panager/services/` | **Business Logic Layer**: 외부 API(Google, GitHub 등) 통신 추상화. | [View Map](src/panager/services/codemap.md) |
| `src/panager/discord/` | **UI Layer**: Discord 봇 핸들러 및 스트리밍 응답 구현. | [View Map](src/panager/discord/codemap.md) |

## Design Patterns
- **Supervisor-Worker (Multi-Agent)**: 중앙 Supervisor가 사용자 의도를 분석하여 전문 워커에게 작업을 할당합니다.
- **Hierarchical Planning**: 복잡한 요청을 도메인별 워커가 처리할 수 있는 소작업으로 분해합니다.
- **Interrupt/Resume**: LangGraph Checkpointer를 활용해 인증(OAuth) 등 중단점이 필요한 워크플로우를 관리합니다.
- **Service-Repository Pattern**: 비즈니스 로직과 데이터베이스/외부 API 통신 로직을 분리합니다.
- **JSON-First Tool Response**: 모든 도구 응답을 정형화된 JSON 문자열로 반환하여 LLM 안정성을 확보합니다.

## Data & Control Flow
1. **Trigger**: Discord 입력, GitHub 웹훅, 또는 내부 스케줄러에 의해 작업 시작.
2. **Analysis**: `supervisor.py`가 의도를 파악하고 적절한 워커를 결정.
3. **Execution**: 워커가 도구(Tools)를 호출하여 실제 작업 수행. 필요 시 인증 중단 발생.
4. **Summary**: 작업 결과를 요약하여 사용자에게 최종 보고.

## Integration Points
- **Discord**: 주요 사용자 인터페이스 (스트리밍 응답 지원).
- **Google Workspace**: 캘린더 및 할 일 목록 연동.
- **GitHub**: 리포지토리 관리 및 푸시 이벤트 웹훅 수신.
- **Notion**: 데이터베이스 기반 기록 관리.
- **PostgreSQL / pgvector**: 상태 저장 및 벡터 기반 시맨틱 메모리.
