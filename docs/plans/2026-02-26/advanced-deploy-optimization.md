# Advanced Build & Deploy Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement zero-downtime deployment and automated rollback for the Panager bot.

**Architecture:** 
- **API**: Add `/health` endpoint for readiness checking.
- **Docker Compose**: Configure `healthcheck` and `start-first` update strategy.
- **GHA**: Enhance `deploy` job with `--wait` and failure-triggered rollback.

**Tech Stack:** FastAPI, Docker Compose, GitHub Actions

---

### Task 1: Add Health Check Endpoint

**Files:**
- Modify: `src/panager/api/main.py`
- Test: `tests/panager/api/test_health.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from panager.api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/panager/api/test_health.py`
Expected: FAIL (404 Not Found)

**Step 3: Implement the /health endpoint**

Add to `src/panager/api/main.py`:
```python
@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

**Step 4: Run test to verify it passes**

**Step 5: Commit**

```bash
git add src/panager/api/main.py
git commit -m "feat: FastAPI에 /health 엔드포인트 추가"
```

---

### Task 2: Configure Docker Compose for Zero-Downtime

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add healthcheck to panager service**

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 10s
  timeout: 5s
  retries: 3
  start_period: 20s
```

**Step 2: Add deploy strategy**

```yaml
deploy:
  update_config:
    order: start-first
    failure_action: rollback
    delay: 5s
```

**Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "refactor: 무중단 배포를 위한 Docker Compose 설정 고도화"
```

---

### Task 3: Enhance GitHub Actions with Auto-Rollback

**Files:**
- Modify: `.github/workflows/dev.yml`

**Step 1: Update Deploy job to use --wait and automated rollback**

1. Modify `docker compose up -d` to `docker compose up -d --wait`.
2. Add a `Rollback` step using `if: failure()`.

```yaml
- name: Deploy
  id: deploy
  run: |
    # ... env setup ...
    ssh ... << 'EOF'
      cd ${{ vars.DEPLOY_PATH }}
      docker compose pull
      if ! docker compose up -d --wait; then
        exit 1
      fi
    EOF

- name: Rollback on Failure
  if: failure() && steps.deploy.outcome == 'failure'
  run: |
    ssh ... << 'EOF'
      cd ${{ vars.DEPLOY_PATH }}
      sed -i "s/IMAGE_TAG=.*/IMAGE_TAG=${{ env.PREVIOUS_SHA }}/" .env
      docker compose up -d --wait
    EOF
```

**Step 2: Commit**

```bash
git add .github/workflows/dev.yml
git commit -m "ci: 배포 실패 시 자동 롤백 로직 추가"
```

---

### Task 4: Verification

**Step 1: Run local docker-compose up --wait**

Verify that the healthcheck correctly reports healthy status.

**Step 2: Push and verify GHA workflow**
