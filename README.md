# AI Quant Research Platform

An AI-powered quantitative research platform for educational and research use.
The MVP will support A-share daily market data, deterministic technical signal
scanning, persisted research results, and a web dashboard.

This project does not connect to brokers, execute trades, or provide investment
recommendations.

## Current Status

Phases 1 through 3 currently provide:

- Minimal FastAPI backend with a liveness endpoint.
- Python scanner command-line shell with no scanning logic.
- React and TypeScript application shell with no dashboard features.
- PostgreSQL, backend, frontend, and scanner Docker Compose definitions.
- Python and frontend formatting, linting, type checking, and test tooling.
- SQLAlchemy 2.x models for stocks, daily prices, scanner runs, versioned signal
  definitions, and detected technical signals.
- Alembic migrations for creating and removing the MVP database schema.
- Validated, transactional CSV ingestion for stock metadata and daily OHLCV
  prices.
- Idempotent PostgreSQL upserts and structured ingestion summaries.

Technical signal scanning logic is not implemented yet.

## Requirements

- Python 3.11, 3.12, or 3.13
- Node.js 22 or newer and npm
- Docker with Docker Compose v2 for the container workflow

The initial setup has been tested with Python 3.11 and Node.js 24.

## Repository Layout

- `backend/`: FastAPI application and backend tests.
- `frontend/`: React and TypeScript application.
- `scanner/`: Command-line scanner package.
- `deployment/`: Docker Compose configuration.
- `docs/`: Product and technical design documents.
- `tests/`: Future cross-component and end-to-end tests.
- `ai/`: Future AI report generation.
- `rag/`: Future retrieval-augmented generation.
- `data/`: Future fixtures and local data workspace.

## Local Setup

Copy `.env.example` to `.env` only when local overrides are needed. Never commit
the resulting `.env`.

### Python

On Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
```

On macOS or Linux:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
```

Start the backend:

```sh
uvicorn backend.app.main:app --reload
```

Verify it at `http://localhost:8000/health`.

Run the scanner shell:

```sh
python -m scanner --help
```

### Frontend

```sh
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`.

## Database Setup and Migrations

The default local connection is:

```text
postgresql+psycopg://ai_quant:local_development_only@localhost:5432/ai_quant
```

Override it with `AQR_DATABASE_URL`. Do not use the example password outside an
isolated local development environment.

Start PostgreSQL with Docker Compose:

```sh
docker compose -f deployment/compose.yaml up -d postgres
```

Apply migrations from the local Python environment:

```sh
alembic upgrade head
alembic current
```

Or run migrations inside the backend container:

```sh
docker compose -f deployment/compose.yaml run --rm backend alembic upgrade head
```

Generate the SQL without connecting to PostgreSQL:

```sh
alembic upgrade head --sql
```

Roll back the most recent migration only against a disposable or intentionally
managed database:

```sh
alembic downgrade -1
```

The initial migration creates:

- `stocks`
- `daily_prices`
- `scanner_runs`
- `signal_definitions`
- `technical_signals`

Application code must use migrations rather than `Base.metadata.create_all()` to
manage persistent databases.

## Market Data Ingestion

The initial provider is a local CSV importer. It does not call a broker or live
market-data service. Import the documented synthetic sample after applying
migrations:

```sh
python -m scanner ingest-csv \
  --stocks-file data/sample/stocks.csv \
  --prices-file data/sample/daily_prices.csv \
  --source synthetic_csv_v1 \
  --expected-through 2026-06-13
```

PowerShell accepts the same command on one line:

```powershell
python -m scanner ingest-csv --stocks-file data/sample/stocks.csv --prices-file data/sample/daily_prices.csv --source synthetic_csv_v1 --expected-through 2026-06-13
```

The command validates the complete batch before writing and imports stocks and
prices in one database transaction. Re-running it updates the existing
(`exchange`, `symbol`) and (`stock_id`, `trade_date`) records instead of creating
duplicates.

Stock CSV required columns:

- `symbol`, `exchange`, `name`
- Optional: `list_date`, `delist_date`, `status`

Daily-price CSV required columns:

- `symbol`, `exchange`, `trade_date`
- `open`, `high`, `low`, `close`, `volume`
- Optional: `amount`

Dates must use `YYYY-MM-DD`. Supported exchanges are `SSE`, `SZSE`, and `BSE`.
The importer rejects malformed, negative, non-finite, duplicate, and invalid
OHLC records. `--expected-through` enables future-date rejection and stale-data
warnings; `--max-staleness-days` defaults to `7`.

The sample files in `data/sample/` are deterministic synthetic data:

- Price adjustment: unadjusted synthetic prices.
- Price and amount denomination: synthetic CNY values.
- Volume unit: shares.
- Stored source identifier: `synthetic_csv_v1`.

These values are development fixtures, not market facts or investment
recommendations.

Run the same sample through the scanner container:

```sh
docker compose -f deployment/compose.yaml --profile tools run --rm scanner \
  ingest-csv \
  --stocks-file data/sample/stocks.csv \
  --prices-file data/sample/daily_prices.csv \
  --source synthetic_csv_v1 \
  --expected-through 2026-06-13
```

### PostgreSQL Integration Test

The default test suite validates models, CSV parsing, constraints,
relationships, and offline migration SQL without requiring a running database.

For a real PostgreSQL migration test, create a disposable database whose name
ends in `_test`:

```powershell
docker compose -f deployment/compose.yaml exec postgres `
  createdb -U ai_quant ai_quant_test

$env:TEST_DATABASE_URL = `
  "postgresql+psycopg://ai_quant:local_development_only@localhost:5432/ai_quant_test"

pytest -m postgres
```

The tests reject database names that do not end in `_test`, apply all
migrations, verify tables and model persistence, exercise constraints, test
idempotent CSV imports and transaction rollback, and then downgrade back to an
empty schema.

### Docker Compose

From the repository root:

```sh
docker compose -f deployment/compose.yaml config
docker compose -f deployment/compose.yaml up --build
```

The default local ports are:

- Frontend: `5173`
- Backend: `8000`
- PostgreSQL: `5432`

Override them with values from `.env` if those ports are already in use.

Run the one-shot scanner container:

```sh
docker compose -f deployment/compose.yaml --profile tools run --rm scanner --help
```

Stop the stack:

```sh
docker compose -f deployment/compose.yaml down
```

Add `--volumes` only when intentionally deleting the local PostgreSQL data
volume.

## Quality Checks

Run Python checks from the repository root:

```sh
pytest
ruff check .
ruff format --check .
mypy backend scanner
```

Run frontend checks from `frontend/`:

```sh
npm run lint
npm run typecheck
npm test
npm run build
npm run format:check
```

## Configuration

Application settings use the `AQR_` environment prefix:

- `AQR_ENVIRONMENT`
- `AQR_BACKEND_HOST`
- `AQR_BACKEND_PORT`
- `AQR_DATABASE_URL`
- `AQR_DATABASE_ECHO`
