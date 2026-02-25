# Dev Pipeline Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce Dev Pipeline execution time from 8m to < 2m by parallelizing jobs and isolating heavy model downloads in Docker layers.

**Architecture:** 
- **Docker**: Move `SentenceTransformer` model download to a standalone stage that only depends on the model name.
- **GHA**: Remove job dependencies between `lint`, `test`, and `build`. Make `deploy` wait for all three.

**Tech Stack:** GitHub Actions, Docker, uv, Python

---

### Task 1: Optimize Dockerfile for Model Caching

**Files:**
- Modify: `Dockerfile`

**Step 1: Refactor Dockerfile to isolate model download**

Modify `Dockerfile` to add a `model-cache` stage and copy it into the final image.

```dockerfile
# --- Stage: Model Downloader ---
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS model-downloader
WORKDIR /model
RUN uv run --with sentence-transformers python -c \
    "from sentence_transformers import SentenceTransformer; \
     SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

# --- Stage 1: Builder ---
# ... (existing builder)
# Add:
COPY --from=model-downloader /root/.cache/huggingface /app/.cache/huggingface
```

**Step 2: Remove redundant uv sync and model download from Builder stage**

**Step 3: Commit changes**

```bash
git add Dockerfile
git commit -m "refactor: Docker 빌드 시 모델 다운로드 레이어 분리 및 최적화"
```

---

### Task 2: Parallelize GitHub Actions Workflow

**Files:**
- Modify: `.github/workflows/dev.yml`

**Step 1: Remove `needs: [lint, test]` from `build` job**

Change line 80:
```yaml
build:
  name: Build & Push (Dev)
  # needs: [lint, test]  <-- Remove this
  runs-on: ubuntu-latest
```

**Step 2: Update `deploy` job to depend on all previous jobs**

Change line 112:
```yaml
deploy:
  name: Deploy to Dev
  needs: [lint, test, build]
  runs-on: ubuntu-latest
```

**Step 3: Remove unnecessary QEMU setup**

Remove lines 88-89 from `dev.yml` as we only build for `linux/amd64`.

**Step 4: Commit changes**

```bash
git add .github/workflows/dev.yml
git commit -m "ci: lint, test, build 작업 병렬화 및 불필요한 QEMU 제거"
```

---

### Task 3: Verification

**Step 1: Verify Dockerfile builds locally with cache**

Run: `docker build --target runtime -t panager:test .`
Check if the model download is skipped on second build.

**Step 2: Push to dev branch and monitor GHA**

Run: `git push origin dev`
Monitor the GHA dashboard for total time.
