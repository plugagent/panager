# Remove ARM Build & Local Docker Setup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** GitHub Actions의 빌드 플랫폼에서 ARM 아키텍처를 제거하여 CI 속도를 개선하고, 로컬에서 코드 수정 시 즉시 반영되는 도커 개발 환경을 구축합니다.

**Architecture:**
- **CI/CD**: `linux/amd64` 단일 플랫폼 빌드로 전환.
- **Local Dev**: `docker-compose.dev.yml`을 사용하여 로컬 코드를 컨테이너에 마운트(Volume)하고, `watchfiles`를 통해 핫 리로드를 지원합니다.

**Tech Stack:** Docker, Docker Compose, GitHub Actions, Makefile.

---

### Task 1: GitHub Actions에서 ARM 빌드 제거

**Files:**
- Modify: `.github/workflows/dev.yml`
- Modify: `.github/workflows/prod-cd.yml`

**Step 1: 플랫폼 설정 수정**
`platforms: linux/amd64,linux/arm64` 섹션을 찾아 `platforms: linux/amd64`로 변경합니다.

**Step 2: Commit**
```bash
git add .github/workflows/dev.yml .github/workflows/prod-cd.yml
git commit -m "refactor: GHA 빌드 플랫폼에서 arm64 제거 (amd64 전용)"
```

---

### Task 2: 로컬 개발용 `docker-compose.dev.yml` 생성

**Files:**
- Create: `docker-compose.dev.yml`

**Step 1: 설정 내용 작성**
- `panager` 서비스: `build: .`, `volumes: [./src:/app/src]`, `command: uv run watchfiles "python -m panager.main" src`
- `db` 서비스: `image: pgvector/pgvector:pg16`, `ports: ["5432:5432"]`
- `migrate` 서비스: 로컬 빌드 기반 마이그레이션 수행.

**Step 2: Commit**
```bash
git add docker-compose.dev.yml
git commit -m "feat: 로컬 개발 전용 docker-compose.dev.yml 추가 (핫 리로드 지원)"
```

---

### Task 3: Makefile 업데이트

**Files:**
- Modify: `Makefile`

**Step 1: 명령어 추가**
- `up-dev`: `docker compose -f docker-compose.dev.yml up -d`
- `down-dev`: `docker compose -f docker-compose.dev.yml down`
- `logs-dev`: `docker compose -f docker-compose.dev.yml logs -f`

**Step 2: Commit**
```bash
git add Makefile
git commit -m "docs: Makefile에 로컬 도커 개발 환경 명령어 추가"
```
