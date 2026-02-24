# Fix Docker "uv" executable not found error Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the `exec: "uv": executable file not found` error when running `make dev-up` by ensuring `uv` and dev dependencies are available in the development container.

**Architecture:** Use a multi-stage Docker build with a dedicated `dev` target. The `dev` target will inherit from the `builder` stage (which already has `uv`) and install dev dependencies. `docker-compose.dev.yml` will be updated to use this `dev` target.

**Tech Stack:** Docker, Docker Compose, uv

---

### Task 1: Modify Dockerfile to add a `dev` stage

**Files:**
- Modify: `/Users/johjun/Documents/plugagent.click/plugagent_lab/panager/Dockerfile`

**Step 1: Read current Dockerfile**
(Already done, but verify context)

**Step 2: Add `dev` stage**
Insert a `dev` stage before the production `runtime` stage. This stage will inherit from `builder` and run `uv sync` to ensure dev dependencies are installed.

```dockerfile
# (After the last builder stage command)
# RUN --mount=type=cache,target=/root/.cache/uv \
#     uv sync --frozen --no-dev

# --- Stage 2: Development ---
FROM builder AS dev

# Install dev dependencies (remove --no-dev)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Runtime settings for dev
USER panager
# CMD is usually overridden by docker-compose.dev.yml, but we can set a default
CMD ["uv", "run", "watchfiles", "python -m panager.main", "src"]

# --- Stage 3: Runtime (Production) ---
# ... (existing production runtime stage)
```

**Step 3: Commit**
```bash
git add Dockerfile
git commit -m "feat: Dockerfile에 개발용 dev 스테이지 추가"
```

---

### Task 2: Update docker-compose.dev.yml to use the `dev` target

**Files:**
- Modify: `/Users/johjun/Documents/plugagent.click/plugagent_lab/panager/docker-compose.dev.yml`

**Step 1: Update `panager` service build config**

```yaml
  panager:
    build:
      context: .
      target: dev  # <--- Add this
    command: uv run watchfiles "python -m panager.main" src
    # ...
```

**Step 2: Update `migrate` service build config (optional but recommended for consistency)**

```yaml
  migrate:
    build:
      context: .
      target: dev  # <--- Add this
    command: alembic upgrade head
    # ...
```

**Step 3: Commit**
```bash
git add docker-compose.dev.yml
git commit -m "fix: docker-compose.dev.yml에서 Dockerfile의 dev 스테이지를 사용하도록 수정"
```

---

### Task 3: Verification

**Step 1: Run `make dev-up`**
Run: `make dev-up`
Expected: Containers start without "uv not found" error.

**Step 2: Check logs**
Run: `make dev-logs`
Expected: `panager` service should be running `watchfiles` and starting the bot.

**Step 3: Commit (if any fixes needed)**
```bash
git commit -m "fix: 개발 환경 도커 설정 검증 및 수정"
```
