FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md requirements.lock ./
COPY backend ./backend
COPY scanner ./scanner
COPY data ./data

RUN pip install --no-cache-dir -r requirements.lock \
    && pip install --no-cache-dir --no-deps .

ENTRYPOINT ["python", "-m", "scanner"]
