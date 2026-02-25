# --- Stage 0: Model Downloader ---
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS model-downloader

WORKDIR /app

# 모델 다운로드를 위한 환경 변수 설정
ENV HF_HOME=/app/.cache/huggingface

# 모델 미리 다운로드 (별도 스테이지에서 수행하여 캐시 최적화)
RUN uv run --with sentence-transformers python -c \
    "from sentence_transformers import SentenceTransformer; \
     SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

# --- Stage 1: Builder ---
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# UV 최적화 설정
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/app/.cache/huggingface

# 의존성 설치 (캐시 활용)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# 다운로드된 모델 복사
COPY --from=model-downloader /app/.cache/huggingface /app/.cache/huggingface

# 소스 코드 복사
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini pyproject.toml uv.lock ./

# 프로젝트 설치 (src-layout 프로젝트를 venv에 설치)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- Stage 2: Development ---
FROM builder AS dev

# 환경 변수 설정
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Install dev dependencies (remove --no-dev)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Runtime settings for dev
RUN adduser --disabled-password --gecos "" panager && \
    mkdir -p /app/logs /app/.cache/huggingface && \
    chown -R panager:panager /app
USER panager
# CMD is usually overridden by docker-compose.dev.yml
CMD ["uv", "run", "watchfiles", "python -m panager.main", "src"]

# --- Stage 3: Runtime ---
FROM python:3.13-slim-bookworm

WORKDIR /app

# 헬스체크(curl) 및 런타임 환경 설정
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 실행 시 필요한 환경 변수
ENV PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/app/.cache/huggingface \
    PYTHONUNBUFFERED=1

# 사용자 및 디렉토리 설정
RUN adduser --disabled-password --gecos "" panager && \
    mkdir -p /app/logs /app/.cache/huggingface && \
    chown -R panager:panager /app

# 빌드 스테이지에서 필요한 파일만 복사
COPY --from=builder --chown=panager:panager /app/.venv /app/.venv
COPY --from=builder --chown=panager:panager /app/src /app/src
COPY --from=builder --chown=panager:panager /app/alembic /app/alembic
COPY --from=builder --chown=panager:panager /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=panager:panager /app/.cache/huggingface /app/.cache/huggingface

USER panager

# 메인 엔트리포인트 (이미 venv/bin이 PATH에 있으므로 직접 python 호출 가능)
CMD ["python", "-m", "panager.main"]
