# Embedding Model Volume Binding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 임베딩 모델을 별도의 Docker 이미지로 분리하고 Init 컨테이너를 통해 볼륨으로 마운트하여 이미지 크기를 줄이고 배포 효율을 높입니다.

**Architecture:** 
1. `Dockerfile.model`을 통해 모델 전용 이미지를 생성합니다.
2. `docker-compose`에 `model-init` 서비스를 추가하여 앱 실행 전 모델 파일을 공유 볼륨(`hf_cache`)으로 복사합니다.
3. 메인 앱(`panager`)은 해당 볼륨을 마운트하여 사용하며, `model-init` 완료 후에만 실행됩니다.

**Tech Stack:** Docker, Docker Compose, Python (sentence-transformers), uv

---

### Task 1: Create Dockerfile.model

**Files:**
- Create: `Dockerfile.model`

**Step 1: Write Dockerfile.model**

```dockerfile
# --- Stage 0: Model Downloader ---
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS downloader

WORKDIR /app

# 모델 다운로드를 위한 환경 변수 설정
ENV HF_HOME=/model-cache

# 모델 미리 다운로드
RUN uv run --with sentence-transformers python -c \
    "from sentence_transformers import SentenceTransformer; \
     SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

# --- Stage 1: Final Image ---
FROM alpine:latest

WORKDIR /model

# 다운로드된 모델 복사
COPY --from=downloader /model-cache /model

# 실행 시 볼륨으로 복사하는 명령
# /app/.cache/huggingface 경로가 볼륨으로 마운트될 것을 가정
CMD ["sh", "-c", "echo 'Copying model to volume...' && mkdir -p /app/.cache/huggingface && cp -a /model/. /app/.cache/huggingface/ && echo 'Done.'"]
```

**Step 2: Commit**

```bash
git add Dockerfile.model
git commit -m "feat: 모델 전용 Dockerfile 추가"
```

---

### Task 2: Update Main Dockerfile

**Files:**
- Modify: `Dockerfile`

**Step 1: Remove model downloading logic from Dockerfile**

기존 `Dockerfile`에서 `model-downloader` 스테이지와 관련된 복사 로직(`COPY --from=model-downloader ...`)을 제거합니다.

```dockerfile
# 1-13라인 삭제 (model-downloader 스테이지)
# 31라인 삭제 (COPY --from=model-downloader ...)
# 86라인 삭제 (COPY --from=builder ... /app/.cache/huggingface)
```

**Step 2: Commit**

```bash
git add Dockerfile
git commit -m "refactor: 메인 Dockerfile에서 모델 다운로드 로직 제거"
```

---

### Task 3: Update docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add model-init service and update panager dependencies**

```yaml
services:
  model-init:
    build:
      context: .
      dockerfile: Dockerfile.model
    volumes:
      - hf_cache:/app/.cache/huggingface
    restart: "no"

  panager:
    # ... 기존 설정 ...
    volumes:
      - panager_logs:/app/logs
      - hf_cache:/app/.cache/huggingface # 볼륨 추가
    depends_on:
      db:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
      model-init:
        condition: service_completed_successfully # 의존성 추가
    # ... 나머지 설정 ...

volumes:
  postgres_data:
  panager_logs:
  hf_cache: # 볼륨 정의 추가
```

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: docker-compose에 model-init 서비스 및 볼륨 추가"
```

---

### Task 4: Update Development and Test Compose Files

**Files:**
- Modify: `docker-compose.dev.yml`
- Modify: `docker-compose.test.yml`

**Step 1: Apply similar changes to dev and test compose files**

`model-init` 서비스를 추가하고 `panager` 서비스의 `volumes`와 `depends_on`을 업데이트합니다.

**Step 2: Commit**

```bash
git add docker-compose.dev.yml docker-compose.test.yml
git commit -m "feat: 개발 및 테스트 환경용 docker-compose 업데이트"
```

---

### Task 5: Verification

**Step 1: Build and Run**

```bash
docker-compose -f docker-compose.dev.yml up --build model-init
docker-compose -f docker-compose.dev.yml up --build panager
```

**Step 2: Verify model is loaded correctly**

`panager` 컨테이너 로그에서 `SentenceTransformer 모델 로딩 완료` 메시지가 나타나는지 확인합니다.
또한 컨테이너 내부에서 모델 파일 존재 여부를 확인합니다.

```bash
docker-compose -f docker-compose.dev.yml exec panager ls -R /app/.cache/huggingface
```
