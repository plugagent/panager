# CI/CD Workflow Redesign Implementation Plan (Final)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** GitHub Environments를 사용하여 운영(Production) 및 개발(Development) 배포 프로세스를 분리하고, 환경별 시크릿 주입 및 대상(사용자/개발자)별 알림 포맷을 차별화합니다.

**Architecture:** 
- 동일 서버 내 격리된 경로(`DEPLOY_PATH`) 및 포트(`PORT`) 사용.
- GitHub Environments (`production`, `development`)를 통한 변수 제어.
- `ENV_FILE` (공통) + `SPECIFIC_ENV` (환경별) 조합으로 `.env` 생성.

**Tech Stack:** GitHub Actions, GitHub Environments, Docker Compose, Tailscale SSH.

---

### Task 1: 인프라 및 환경 예시 파일 업데이트

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

**Step 1: `docker-compose.yml` 수정**
- `panager` 서비스의 포트 설정을 `"${PORT:-8000}:8000"`으로 변경하여 외부 주입 허용.

**Step 2: `.env.example` 수정**
- `PORT` 변수 추가 및 용도(8000/8080) 주석 작성.

**Step 3: Commit**
`refactor: 포트 가변화 및 .env.example 업데이트`

---

### Task 2: CI 워크플로 트리거 확장

**Files:**
- Modify: `.github/workflows/ci.yml`

**Step 1: `dev` 브랜치 추가**
- `on.pull_request.branches`에 `dev` 추가.

**Step 2: Commit**
`ci: dev 브랜치 검증 추가`

---

### Task 3: CD 워크플로 재설계 (Environments & 차별화된 알림)

**Files:**
- Modify: `.github/workflows/cd.yml`

**Step 1: 환경 설정 및 배포 준비**
- `environment: ${{ github.ref_name == 'main' && 'production' || 'development' }}` 설정.
- `build` 잡에서 이미지 태그 결정 (`main` -> `latest`, `dev` -> `dev`).

**Step 2: `.env` 생성 로직 수정**
- `secrets.ENV_FILE` (공통) 작성 후 `secrets.SPECIFIC_ENV` (환경별) 추가.
- `IMAGE_TAG` 추가.

**Step 3: 알림 로직 차별화**
- **운영 성공 (`main`)**: `SUCCESS_WEBHOOK_URL`에 단순 텍스트 전송.
- **개발 성공 (`develop`)**: `SUCCESS_WEBHOOK_URL`에 기술 상세 Embed 전송.
- **모든 실패**: `FAILURE_WEBHOOK_URL`에 에러 로그 및 롤백 정보 Embed 전송.

**Step 4: Commit**
`feat: 환경별 시크릿 주입 및 대상별 알림 포맷 차별화`

---

### Task 4: Rollback 워크플로 업데이트

**Files:**
- Modify: `.github/workflows/rollback.yml`

**Step 1: 환경 선택 입력 추가**
- `workflow_dispatch`에 `environment` (production/development) 선택 추가.
- `environment: ${{ github.event.inputs.environment }}` 적용.

**Step 2: 동적 경로 및 시크릿 적용**
- `vars.DEPLOY_PATH` 및 해당 환경의 시크릿을 사용하도록 배포 단계 수정.

**Step 3: Commit**
`feat: 환경 선택형 롤백 지원`

---

### ⚠️ GitHub UI 설정 가이드 (작업 전 완료 필수)

#### 1. Repository Secrets (공통 - ENV_FILE)
모든 환경에서 공통으로 사용하는 설정입니다.
- `ENV_FILE`: `.env.example`의 **1. Common Settings** 섹션 내용 전체

#### 2. Environments 설정 (환경별 - SPECIFIC_ENV)

| 항목 | Environment: `production` | Environment: `development` |
| :--- | :--- | :--- |
| **Secrets: `SPECIFIC_ENV`** | `.env.example` 2번 섹션 (Port 8000용) | `.env.example` 2번 섹션 (Port 8080용) |
| **Secrets: `SUCCESS_WEBHOOK_URL`** | 사용자 채널 웹훅 | 개발자 채널 웹훅 |
| **Secrets: `FAILURE_WEBHOOK_URL`** | 개발자 채널 웹훅 | 개발자 채널 웹훅 |
| **Variables: `DEPLOY_PATH`** | `~/app/panager` | `~/app/panager-dev` |
