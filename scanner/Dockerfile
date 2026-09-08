FROM ghcr.io/astral-sh/uv:0.12.10 AS uv

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml README.md uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY ai ./ai
COPY backend ./backend
COPY rag ./rag
COPY scanner ./scanner
COPY data ./data

RUN uv sync --frozen --no-dev --no-editable

ENTRYPOINT ["/app/.venv/bin/python", "-m", "scanner"]
