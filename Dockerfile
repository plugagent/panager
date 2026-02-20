FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

WORKDIR /app

ENV HF_HOME=/app/.cache/huggingface
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN adduser --disabled-password --gecos "" panager

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY --chown=panager:panager src/ ./src/
COPY --chown=panager:panager alembic/ ./alembic/
COPY --chown=panager:panager alembic.ini pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

RUN --mount=type=cache,target=/root/.cache/huggingface \
    HF_HOME=/root/.cache/huggingface \
    uv run python -c \
    "from sentence_transformers import SentenceTransformer; \
     SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

USER panager

CMD ["uv", "run", "python", "-m", "panager.bot.client"]
