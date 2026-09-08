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

COPY alembic.ini ./
COPY ai ./ai
COPY backend ./backend
COPY rag ./rag
COPY scanner ./scanner

RUN uv sync --frozen --no-dev --no-editable

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
