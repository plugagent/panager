# DB 통합 및 테스트 환경 최적화 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `docker-compose.test.yml`을 제거하고 `dev` DB 컨테이너(5432 포트)를 테스트에서 공용으로 사용하도록 수정합니다.

**Architecture:** `Makefile`의 DB 시작 및 테스트 명령어를 `docker-compose.dev.yml` 기준으로 통일하고, 테스트 코드 내의 접속 정보를 업데이트합니다.

**Tech Stack:** Docker Compose, Makefile, Pytest, GitHub Actions

---

### Task 1: 인프라 설정 통합 및 Makefile 수정

**Files:**
- Modify: `Makefile`
- Delete: `docker-compose.test.yml`

**Step 1: Makefile 수정**
`db`, `test`, `migrate-test` 타겟을 `5432` 포트와 `panager` DB를 사용하도록 수정합니다.

**Step 2: docker-compose.test.yml 삭제**
`rm docker-compose.test.yml`

**Step 3: DB 실행 확인**
Run: `make db`
Expected: `docker-compose.dev.yml`의 `db` 서비스가 5432 포트에서 정상 실행됨.

**Step 4: Commit**
```bash
git add Makefile
git rm docker-compose.test.yml
git commit -m "chore: docker-compose.test.yml 제거 및 Makefile DB 설정 통합"
```

---

### Task 2: 테스트 코드 내 DB 접속 정보 수정

**Files:**
- Modify: `tests/test_db_connection.py`
- Modify: `tests/services/test_memory.py`

**Step 1: tests/test_db_connection.py 수정**
포트를 `5432` -> `5432`, DB명을 `panager` -> `panager`로 변경합니다.

**Step 2: tests/services/test_memory.py 수정**
동일하게 접속 정보를 수정합니다.

**Step 3: 테스트 실행 및 확인**
Run: `make test`
Expected: 모든 테스트 통과

**Step 4: Commit**
```bash
git add tests/
git commit -m "test: 테스트 코드 내 DB 접속 정보 업데이트 (5432 -> 5432)"
```

---

### Task 3: CI/CD 워크플로우 수정

**Files:**
- Modify: `.github/workflows/dev.yml`
- Modify: `.github/workflows/prod-ci.yml`

**Step 1: 워크플로우 파일 수정**
PostgreSQL 서비스 컨테이너의 `POSTGRES_DB`를 `panager`로 변경합니다.

**Step 2: Commit**
```bash
git add .github/workflows/
git commit -m "chore: CI 워크플로우 DB 이름 통일 (panager -> panager)"
```
