# Design Doc: Repo Reflection to Notion (Webhook-driven)

## 1. Overview
사용자가 GitHub 레포지토리에 푸시를 하면, 에이전트가 이를 감지하여 사용자에게 회고를 제안하고, 사용자의 답변을 Notion 등 원하는 외부 서비스로 전송하는 기능을 추가합니다. 이 시스템은 서비스별 독립된 워커(Sub-graph) 구조를 채택하여 향후 다른 서비스(Slack, Jira 등)로의 확장이 용이하도록 설계합니다.

## 2. Architecture

### 2.1 Component Overview
- **FastAPI Webhook Handler**: GitHub Push 이벤트를 수신하고 서명을 검증합니다.
- **AgentState (Memory)**: `pending_reflections` 리스트를 통해 사용자의 답변을 기다리는 보류 중인 작업들을 관리합니다.
- **GithubWorker**: GitHub 활동 분석 및 Webhook 관리를 담당하는 하위 그래프.
- **NotionWorker**: Notion 데이터베이스에 회고 내용을 기록하는 하위 그래프.
- **Action Registry**: (Optional) 워커 내부에서 다양한 액션 플러그인을 동적으로 호출하기 위한 구조.

### 2.2 Data Flow
1. **Trigger**: GitHub Push -> FastAPI `/api/webhooks/github` 수신.
2. **Inject**: `bot.trigger_task` 호출 -> `AgentState`에 푸시 정보 삽입 및 시스템 메시지 발생.
3. **Notify**: 에이전트가 Discord DM으로 사용자에게 회고 작성 요청.
4. **Respond**: 사용자가 텍스트로 회고 내용 답변.
5. **Route**: Supervisor가 답변의 의도를 파악하여 `NotionWorker` (또는 다른 서비스 워커)로 전달.
6. **Action**: `NotionWorker`가 인증 확인 후 Notion API를 호출하여 페이지 생성.

## 3. Detailed Specifications

### 3.1 OAuth & Auth
- **GitHub**: `repo`, `admin:repo_hook` 스코프 필요.
- **Notion**: `Read content`, `Insert content` 권한 필요.
- **Token Storage**: `github_tokens`, `notion_tokens` 테이블을 생성하여 유저별 토큰 관리.

### 3.2 Database Schema Changes
- `github_tokens`, `notion_tokens` 테이블 추가.
- `AgentState`에 `pending_reflections` 필드 추가 (JSON/List).

### 3.3 GitHub Webhook Handling
- **Endpoint**: `/api/webhooks/github`
- **Security**: `X-Hub-Signature-256` 헤더를 통한 HMAC SHA256 검증 필수.
- **Payload Extraction**: `repository.full_name`, `ref`, `commits` 정보를 추출하여 요약 생성에 활용.

### 3.4 Notion Integration
- **Target**: 사용자가 선택한 Notion Database.
- **Format**: 
    - Title: `[Repo Name] Reflection - YYYY-MM-DD`
    - Properties: `Date`, `Repository`, `Tags` (AI 생성).
    - Content: AI 요약(커밋 내역) + 사용자 회고 본문.

## 4. Scalability (Future Actions)
새로운 외부 서비스(예: Slack)를 추가하려면:
1. `src/panager/agent/slack/graph.py` (SlackWorker) 생성.
2. `src/panager/services/slack.py` 인증 로직 추가.
3. Supervisor의 라우팅 로직에 SlackWorker 등록.

## 5. Success Criteria
- [ ] GitHub 푸시 시 Discord 알림이 정상적으로 오는지 확인.
- [ ] 사용자의 대답이 Notion 데이터베이스에 페이지로 생성되는지 확인.
- [ ] 연동되지 않은 상태에서 실행 시 OAuth 인증 프로세스가 유도되는지 확인.
