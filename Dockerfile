FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

WORKDIR /app

ENV HF_HOME=/app/.cache/huggingface
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN adduser --disabled-password --gecos "" panager

# 의존성 설치 (레이어 캐시 최적화)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY src/ ./src/
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# 임베딩 모델 사전 다운로드
RUN uv run python -c \
    "from sentence_transformers import SentenceTransformer; \
     SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

RUN chown -R panager:panager /app

USER panager

CMD ["uv", "run", "python", "-m", "panager.bot.client"]
