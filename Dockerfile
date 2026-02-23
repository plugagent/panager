# --- Stage 1: Builder ---
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS builder

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

# 모델 미리 다운로드 (빌드 시점에 포함)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv run python -c \
    "from sentence_transformers import SentenceTransformer; \
     SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

# 소스 코드 복사 및 프로젝트 설치
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- Stage 2: Runtime ---
FROM python:3.13-slim-bookworm

WORKDIR /app

# 실행 시 필요한 환경 변수
ENV PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/app/.cache/huggingface \
    PYTHONUNBUFFERED=1

# 사용자 생성
RUN adduser --disabled-password --gecos "" panager

# 빌드 스테이지에서 필요한 파일만 복사
COPY --from=builder --chown=panager:panager /app/.venv /app/.venv
COPY --from=builder --chown=panager:panager /app/src /app/src
COPY --from=builder --chown=panager:panager /app/alembic /app/alembic
COPY --from=builder --chown=panager:panager /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=panager:panager /app/.cache/huggingface /app/.cache/huggingface

USER panager

# 메인 엔트리포인트 (이미 venv/bin이 PATH에 있으므로 직접 python 호출 가능)
CMD ["python", "-m", "panager.main"]
