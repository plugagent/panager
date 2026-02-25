# Repo Reflection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** GitHub 푸시 시 에이전트가 회고를 제안하고, 사용자의 답변을 Notion 데이터베이스에 저장하는 확장 가능한 워커 기반 시스템 구축.

**Architecture:** GitHub Webhook을 통해 이벤트를 수신하고, `AgentState`에 보류 중인 회고를 기록합니다. 사용자의 답변에 따라 Supervisor가 `GithubWorker` 또는 `NotionWorker`로 라우팅하여 작업을 처리합니다.

**Tech Stack:** Python 3.13, LangGraph, FastAPI, PostgreSQL (psycopg), httpx.

---

### Task 1: Database Schema Expansion
OAuth 토큰 저장을 위한 테이블을 추가합니다.

**Files:**
- Create: `alembic/versions/xxxx_add_github_notion_tokens.py` (Actual filename will vary)

**Step 1: Create migration file**
Run: `uv run alembic revision -m "add github and notion tokens"`

**Step 2: Define schema in migration**
```python
def upgrade():
    op.create_table(
        'github_tokens',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('access_token', sa.String(), nullable=False),
        sa.Column('refresh_token', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table(
        'notion_tokens',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('access_token', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('user_id')
    )

def downgrade():
    op.drop_table('notion_tokens')
    op.drop_table('github_tokens')
```

**Step 3: Apply migration**
Run: `make migrate-test`

**Step 4: Commit**
```bash
git add alembic/versions/
git commit -m "feat: github 및 notion 토큰 저장을 위한 DB 스키마 추가"
```

---

### Task 2: GitHub & Notion Services Implementation
OAuth 처리 및 API 호출을 담당하는 서비스를 구현합니다.

**Files:**
- Create: `src/panager/services/github.py`
- Create: `src/panager/services/notion.py`
- Modify: `src/panager/core/config.py` (설정 추가)

**Step 1: Define Settings**
`Settings` 클래스에 `GITHUB_CLIENT_ID`, `NOTION_CLIENT_ID` 등 추가.

**Step 2: Implement GitHub Service**
`GoogleService` 패턴을 따라 `get_auth_url`, `exchange_code`, `get_client` 구현.

**Step 3: Implement Notion Service**
Notion API(`notion-client`)를 사용하는 서비스 구현.

**Step 4: Commit**
```bash
git commit -m "feat: GitHub 및 Notion 서비스 레이어 구현"
```

---

### Task 3: FastAPI Webhook Handler
GitHub Push 이벤트를 수신하는 엔드포인트를 구현합니다.

**Files:**
- Create: `src/panager/api/webhooks.py`
- Modify: `src/panager/api/app.py` (라우터 등록)

**Step 1: Implement Signature Validation**
`hmac.compare_digest`를 사용하여 `X-Hub-Signature-256` 검증.

**Step 2: Implement Push Handler**
Payload에서 `repository`, `ref`, `commits`를 추출하고 `bot.trigger_task`를 통해 에이전트 실행.

**Step 3: Test Webhook**
`pytest`를 사용하여 가짜 시그니처와 페이로드로 200 OK가 오는지 테스트.

**Step 4: Commit**
```bash
git commit -m "feat: GitHub Webhook 핸들러 및 보안 검증 추가"
```

---

### Task 4: Agent State & Worker Registration
`AgentState`를 확장하고 새로운 워커들을 그래프에 연결합니다.

**Files:**
- Modify: `src/panager/agent/state.py`
- Create: `src/panager/agent/github/graph.py`
- Create: `src/panager/agent/notion/graph.py`
- Modify: `src/panager/agent/workflow.py` (그래프 통합)

**Step 1: Add pending_reflections to AgentState**
```python
class AgentState(TypedDict):
    ...
    pending_reflections: Annotated[list[dict], operator.add]
```

**Step 2: Implement NotionWorker**
`save_to_notion` 도구를 가진 전용 워커 그래프 구축.

**Step 3: Implement GithubWorker**
활동 분석 및 Webhook 관리를 위한 워커 그래프 구축.

**Step 4: Update Supervisor**
사용자 답변에 `notion`, `저장`, `기록` 등이 포함되면 `notion_worker`로 보내도록 라우팅 로직 수정.

**Step 5: Commit**
```bash
git commit -m "feat: NotionWorker, GithubWorker 추가 및 Supervisor 라우팅 업데이트"
```

---

### Task 5: End-to-End Verification
전체 흐름이 정상 작동하는지 확인합니다.

**Step 1: Test Auth Flow**
"노션 연동해줘" -> 인증 링크 생성 -> 콜백 -> 토큰 저장 확인.

**Step 2: Test Reflection Flow**
`trigger_task` 모킹 -> 에이전트 질문 -> 사용자 답변 -> Notion에 페이지 생성 확인.

**Step 3: Final Commit**
```bash
git commit -m "feat: Repo Reflection to Notion 기능 구현 완료"
```
