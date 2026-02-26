# 환경별 DB 포트 동기화 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `POSTGRES_PORT` 변수를 사용하여 DB 컨테이너 포트와 앱 접속 포트를 동기화하고 환경 간 충돌을 방지합니다.

**Architecture:** Docker Compose의 `PGPORT` 환경 변수를 사용하여 컨테이너 내부 포트를 변경하고, 이를 호스트 포트 및 애플리케이션 접속 포트와 일치시킵니다.

**Tech Stack:** Docker Compose, YAML, Makefile

---

### Task 1: Docker Compose 파일 수정 (Dev & Prod)

**Files:**
- Modify: `docker-compose.dev.yml`
- Modify: `docker-compose.yml`

**Step 1: docker-compose.dev.yml 수정**
`db` 서비스에 `PGPORT` 변수를 추가하고 `ports` 및 `healthcheck` 설정을 업데이트합니다.

```yaml
  db:
    # ... 기존 설정
    environment:
      - PGPORT=${POSTGRES_PORT:-5432}
    ports:
      - "${POSTGRES_PORT:-5432}:${POSTGRES_PORT:-5432}"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB -p ${POSTGRES_PORT:-5432}"]
    # ...
```

**Step 2: docker-compose.yml 수정**
동일한 로직을 프로덕션용 파일에도 적용합니다.

**Step 3: 설정 검증**
Run: `docker compose -f docker-compose.dev.yml config`
Expected: 유효한 YAML 구조 확인

**Step 4: Commit**
```bash
git add docker-compose.dev.yml docker-compose.yml
git commit -m "chore: Docker Compose DB 포트 가변화 및 PGPORT 동기화 설정 적용"
```

---

### Task 2: Makefile 및 환경 설정 업데이트

**Files:**
- Modify: `.env.example`
- Modify: `Makefile`

**Step 1: .env.example 수정**
`POSTGRES_PORT`에 대한 주석과 설명을 추가합니다.

**Step 2: Makefile 수정**
모든 DB 관련 명령어에서 포트 번호가 환경 변수를 올바르게 따르는지 확인하고 필요시 수정합니다.

**Step 3: 로컬 실행 테스트 (기본 포트 5432)**
Run: `make db`
Expected: 5432 포트에서 정상 실행

**Step 4: 로컬 실행 테스트 (커스텀 포트 5433)**
Run: `POSTGRES_PORT=5433 make db`
Expected: 5433 포트에서 정상 실행

**Step 5: Commit**
```bash
git add .env.example Makefile
git commit -m "chore: Makefile 및 .env.example 내 DB 포트 설정 가이드 추가"
```

---

### Task 3: 최종 통합 테스트

**Step 1: 전체 테스트 실행**
Run: `make test`
Expected: 모든 테스트 통과 (기본 포트 5432 기준)

**Step 2: 커스텀 포트 기반 테스트 실행**
Run: `POSTGRES_PORT=5434 make test`
Expected: 5434 포트로 DB 실행 및 테스트 정상 완료
