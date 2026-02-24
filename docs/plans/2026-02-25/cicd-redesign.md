# CI/CD Workflow Redesign Implementation Plan (Final)

**Goal:** GitHub Environments를 사용하여 운영(Production) 및 개발(Development) 배포 프로세스를 분리하고, 환경별 최적화된 워크플로를 구축합니다.

**Architecture:** 
- **Development (dev)**: 통합 파이프라인 (Lint + Test + Build + Deploy). 빠른 피드백과 자동화된 개발 환경 배포.
- **Production (main)**: 분리형 파이프라인. PR 시 검증(`prod-ci`), 머지 시 배포(`prod-cd`)로 안정성 확보.
- **Infrastructure**: 동일 서버 내 격리된 경로(`DEPLOY_PATH`) 및 포트(`PORT`) 사용. GitHub Environments 기반 변수 제어.

**Tech Stack:** GitHub Actions, GitHub Environments, Docker Compose, Tailscale SSH.

---

### 1. 워크플로 구성

#### **A. `dev.yml` (개발 통합 파이프라인)**
- **Trigger**: `push` to `dev`
- **Jobs**: 
  1. `lint` & `test`: 코드 품질 및 로직 검증 (실패 시 중단)
  2. `build`: Docker 이미지 빌드 및 `ghcr.io` 푸시 (`dev` 태그)
  3. `deploy`: 개발 서버(`~/app/panager-dev`) 배포 및 8080 포트 적용
- **Notification**: 개발자 채널에 상세 기술 정보(SHA, 로그 링크 등)를 Embed 형태로 전송.

#### **B. `prod-ci.yml` (운영 PR 검증)**
- **Trigger**: `pull_request` to `main`
- **Jobs**: `lint`, `test`, `build-check` (빌드 가능 여부만 확인)
- **Goal**: 운영 브랜치 머지 전 안정성 최종 관문 역할.

#### **C. `prod-cd.yml` (운영 배포)**
- **Trigger**: `push` to `main` (머지 완료 시)
- **Jobs**: 
  1. `build`: Docker 이미지 빌드 및 `ghcr.io` 푸시 (`latest` 태그)
  2. `deploy`: 운영 서버(`~/app/panager`) 배포 및 8000 포트 적용
- **Notification**: 성공 시 사용자 채널에 간결한 메시지 전송, 실패 시 개발자 채널에 에러 알림.

#### **D. `rollback.yml` (공통 수동 롤백)**
- **Trigger**: `workflow_dispatch` (환경 및 대상 SHA 선택)
- **Goal**: 특정 환경을 원하는 커밋 버전으로 즉시 복구.

---

### 2. 인프라 및 환경 설정

#### **docker-compose.yml**
- 포트 설정을 `"${PORT:-8000}:8000"`으로 가변화하여 환경별 충돌 방지.

#### **.env.example**
- 공통 설정(Common)과 환경별 설정(Environment Specific) 섹션을 분리하여 가이드 제공.

---

### ⚠️ GitHub UI 설정 가이드

#### 1. Repository Secrets (공통 - `ENV_FILE`)
- 모든 환경에서 공통으로 사용하는 설정 (예: `LLM_MODEL`, `LOG_PATH` 등).

#### 2. Environments 설정 (환경별)

| 항목 | Environment: `production` | Environment: `development` |
| :--- | :--- | :--- |
| **Secrets: `SPECIFIC_ENV`** | `PORT=8000` 및 운영 DB 비번 등 | `PORT=8080` 및 개발 DB 비번 등 |
| **Secrets: `SUCCESS_WEBHOOK_URL`** | **사용자 채널** 웹훅 | **개발자 채널** 웹훅 |
| **Secrets: `FAILURE_WEBHOOK_URL`** | **개발자 채널** 웹훅 | **개발자 채널** 웹훅 |
| **Variables: `DEPLOY_PATH`** | `~/app/panager` | `~/app/panager-dev` |
