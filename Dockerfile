FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_CACHE_DIR=/root/.cache/uv
ENV HF_HOME=/root/.cache/huggingface

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

RUN --mount=type=cache,target=/root/.cache/huggingface \
    uv run python -c \
        "from sentence_transformers import SentenceTransformer; \
         SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

# ---- 최종 이미지 ----
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

WORKDIR /app

ENV XDG_CACHE_HOME=/home/panager/.cache
ENV HF_HOME=/home/panager/.cache/huggingface
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_CACHE_DIR=/root/.cache/uv

RUN adduser --disabled-password --gecos "" panager

COPY --from=builder --chown=panager:panager /app /app
COPY --from=builder --chown=panager:panager /root/.cache/huggingface /home/panager/.cache/huggingface

USER panager

CMD ["uv", "run", "python", "-m", "panager.bot.client"]
