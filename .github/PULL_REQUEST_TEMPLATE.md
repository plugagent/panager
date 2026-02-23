## 변경 사항 (Type of Change)
- [ ] ✨ feat (신규 기능)
- [ ] 🐛 fix (버그 수정)
- [ ] 📝 docs (문서 수정)
- [ ] 🎨 style (코드 포맷팅, 세미콜론 누락 등, 기능 변경 없음)
- [ ] ♻️ refactor (코드 리팩토링, 기능 변경 없음)
- [ ] ✅ test (테스트 추가/수정)
- [ ] 🏗️ build / ⚙️ chore (빌드 스크립트, 패키지 매니저 설정 등)

## 요약 (Summary)
<!-- 변경 사항의 목적과 주요 내용을 간략히 설명해주세요. -->

## 상세 변경 내역 (Detailed Changes)

### 🤖 Discord / Bot
- <!-- src/panager/discord, src/panager/api 관련 변경 사항 -->

### 🧠 Agent / Workflow
- <!-- src/panager/agent 관련 변경 사항 (tools, state 포함) -->

### 🔌 Services / Integrations
- <!-- src/panager/services, src/panager/integrations 관련 변경 사항 (Google, Memory 등) -->

### ⚙️ Core / Infra / DB / Scheduler
- <!-- src/panager/core, src/panager/db, src/panager/scheduler, Docker, Alembic 등 -->

## 배포 및 인프라 (Deployment & Infra)
<!-- Tailscale, Docker, 환경 변수 등 배포와 관련된 변경 사항이 있다면 적어주세요. -->
- [ ] 새로운 환경 변수가 추가됨 (비밀 저장소 설정 필요)
- [ ] DB 마이그레이션이 필요함 (Alembic)
- [ ] Docker 이미지 빌드/푸시 관련 변경 사항 있음
- [ ] Tailscale/SSH 운영 서버 접근 관련 변경 사항 있음

## 체크리스트 (Checklist)
- [ ] 셀프 리뷰를 수행했습니다.
- [ ] `uv run ruff check src/`로 린트 에러가 없음을 확인했습니다.
- [ ] `uv run ruff format src/`로 코드 포맷을 맞췄습니다.
- [ ] 관련 테스트를 모두 통과했습니다 (`make test`).
- [ ] 필요한 경우 관련 문서(AGENTS.md, docs/ 등)를 업데이트했습니다.
- [ ] 커밋 메시지가 컨벤션(Conventional Commits)을 따릅니다.
