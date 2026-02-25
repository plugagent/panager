# Manual Model Build Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 임베딩 모델 빌드를 별도의 `model.yml`로 분리하여 수동 트리거로 관리하고, 앱 배포와 모델 배포의 태그를 분리하여 운영 효율을 높입니다.

**Architecture:** 
1. `.github/workflows/model.yml` 추가: `workflow_dispatch`를 사용하여 GHCR에 `panager-model-init` 이미지를 푸시합니다.
2. `docker-compose.yml` 수정: 모델 이미지 태그를 `MODEL_IMAGE_TAG` 환경 변수로 분리합니다.
3. `dev.yml`, `prod-cd.yml` 수정: 배포 시 `MODEL_IMAGE_TAG`를 참조하도록 업데이트합니다.
4. `Makefile`, `AGENTS.md`, `.dockerignore` 업데이트: 새로운 빌드 구조 반영.

**Tech Stack:** GitHub Actions, Docker, Docker Compose

---

### Task 1: Create model.yml Workflow

**Files:**
- Create: `.github/workflows/model.yml`

**Step 1: Write model.yml**

```yaml
name: Build & Push Model Image

on:
  workflow_dispatch:
    inputs:
      tag:
        description: 'Image tag (e.g., v1, latest)'
        required: true
        default: 'latest'

jobs:
  build:
    name: Build & Push (Model)
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: Dockerfile.model
          push: true
          tags: |
            ghcr.io/${{ github.repository }}-model-init:${{ github.event.inputs.tag }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Step 2: Commit**

```bash
git add .github/workflows/model.yml
git commit -m "feat: 모델 빌드 수동 트리거 워크플로 추가"
```

---

### Task 2: Separate Model Tag in Docker Compose

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.dev.yml`

**Step 1: Update image tag for model-init**

`docker-compose.yml`:
```yaml
  model-init:
    image: ghcr.io/plugagent/panager-model-init:${MODEL_IMAGE_TAG:-latest}
    # ...
```

`docker-compose.dev.yml`:
```yaml
  model-init:
    image: ghcr.io/plugagent/panager-model-init:${MODEL_IMAGE_TAG:-latest}
    # ...
```

**Step 2: Commit**

```bash
git add docker-compose.yml docker-compose.dev.yml
git commit -m "refactor: 모델 이미지 태그 환경변수 분리 (MODEL_IMAGE_TAG)"
```

---

### Task 3: Update CD Workflows to Support MODEL_IMAGE_TAG

**Files:**
- Modify: `.github/workflows/dev.yml`
- Modify: `.github/workflows/prod-cd.yml`

**Step 1: Update Deployment Step to include MODEL_IMAGE_TAG**

배포 시 서버의 `.env` 파일에 `MODEL_IMAGE_TAG`를 기록하도록 수정합니다. 기본값은 `latest`로 설정하거나 별도의 `vars.MODEL_IMAGE_TAG`를 사용할 수 있게 합니다.

**Step 2: Commit**

```bash
git add .github/workflows/dev.yml .github/workflows/prod-cd.yml
git commit -m "feat: CD 워크플로에 MODEL_IMAGE_TAG 반영"
```

---

### Task 4: Update Documentation and Helper Tools

**Files:**
- Modify: `Makefile`
- Modify: `AGENTS.md`
- Modify: `.dockerignore`

**Step 1: Update Makefile commands**
`dev`, `up` 등에서 `MODEL_IMAGE_TAG`를 지원하도록 수정.

**Step 2: Update .dockerignore**
`.cache/` 디렉토리를 제외하여 빌드 컨텍스트 최적화.

**Step 3: Update AGENTS.md**
모델 빌드 방식 및 수동 트리거 안내 추가.

**Step 4: Commit**

```bash
git add Makefile AGENTS.md .dockerignore
git commit -m "docs: 모델 빌드 구조 변경에 따른 문서 및 도구 최신화"
```

---

### Task 5: Final Verification

**Step 1: Config Validation**

```bash
docker compose config
```

**Step 2: GitHub Actions Syntax Check**
(LSP 또는 로컬 도구가 있다면 실행)
