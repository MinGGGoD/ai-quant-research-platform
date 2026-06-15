# AI Quant Research Platform

An AI-powered quantitative research platform for educational and research use.
The MVP will support A-share daily market data, deterministic technical signal
scanning, persisted research results, and a web dashboard.

This project does not connect to brokers, execute trades, or provide investment
recommendations.

## Current Status

Phases 1 through 6 provide the local MVP. Phases 7 and 8 add optional AI and
research-document retrieval extensions:

- FastAPI liveness, readiness, stock, price, scanner-run, and signal endpoints.
- Python scanner CLI for market-data ingestion and technical signal detection.
- Responsive React and TypeScript research dashboard.
- PostgreSQL, backend, frontend, and scanner Docker Compose definitions.
- Python and frontend formatting, linting, type checking, and test tooling.
- SQLAlchemy 2.x models for stocks, daily prices, scanner runs, versioned signal
  definitions, and detected technical signals.
- Alembic migrations for creating and removing the MVP database schema.
- Validated, transactional AShareHub and CSV ingestion for stock metadata and
  daily OHLCV prices.
- Idempotent PostgreSQL upserts and structured ingestion summaries.
- Versioned `moving_average_cross`, `recent_breakout`, and `volume_spike`
  research signals.
- Persisted scanner-run lifecycle, matched evidence, warnings, and failures.
- Pydantic API responses, pagination, symbol lookup, and structured API errors.
- Stock search and selection, SVG daily K-line and volume charts, stored
  technical signals, and recent scanner-run history.
- Two-year default chart periods with user-triggered, trade-calendar-aware
  incremental AShareHub synchronization and PostgreSQL caching.
- Provider-neutral research-note generation from stored stock details, recent
  price summaries, and detected technical signals.
- Persisted note provenance, model metadata, prompt versions, and source
  context with an output safety gate.
- Local `.txt`, `.md`, and text-based `.pdf` document ingestion with chunking,
  pgvector storage, semantic retrieval, filters, and citations.

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
- `ai/`: Provider-neutral research-note contracts, prompts, safety checks, and
  OpenAI-compatible generation.
- `rag/`: Document loading, chunking, embedding abstractions, and retrieval.
- `data/`: Future fixtures and local data workspace.

## Local Setup

Copy `.env.example` to `.env` only when local overrides are needed. Never commit
the resulting `.env`.

### Bash Helper Scripts

The repository root contains Bash wrappers for the common local workflows.
They work with Git Bash or WSL on Windows and ordinary Bash on macOS or Linux.

First-time local dependency setup:

```sh
bash setup.sh
```

Build images, start PostgreSQL, apply migrations, and start the backend and
frontend:

```sh
bash start.sh
```

On Windows, `start.sh` attempts to launch Docker Desktop when it is installed
but not currently running. PowerShell's `bash` command may open WSL; the helper
scripts detect that case and use Docker Desktop's Windows CLI directly, so
Docker Desktop's per-distribution WSL integration is not required.

Use the existing images for a faster restart when application dependencies have
not changed:

```sh
bash start.sh --no-build
```

Other common commands:

```sh
bash status.sh
bash logs.sh
bash logs.sh backend
bash migrate.sh
bash restart.sh --no-build
bash stop.sh
bash test.sh
bash test.sh frontend
bash scanner.sh --help
```

`stop.sh` preserves the PostgreSQL data volume. These scripts intentionally do
not provide an automatic volume-deletion command.

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

The dashboard reads `VITE_API_BASE_URL`, which defaults to
`http://localhost:8000`. Start PostgreSQL and the backend first:

```powershell
docker compose -f deployment/compose.yaml up -d postgres backend
cd frontend
npm run dev
```

The dashboard provides:

- Paginated active-stock search and selection.
- Up to 250 recent daily K-line and volume records for the selected stock.
- Stored technical signals with deterministic matched values and explanations.
- The eight most recent scanner runs with market dates and summary counts.
- Loading, empty, backend-error, retry, and responsive narrow-screen states.

The chart displays exactly the historical records returned by the API. A short
history, including a single available day, remains visibly sparse and is not
expanded into an implied trend.

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
- `daily_price_sync_ranges`
- `scanner_runs`
- `signal_definitions`
- `technical_signals`

Application code must use migrations rather than `Base.metadata.create_all()` to
manage persistent databases.

## Market Data Ingestion

The primary Phase 3 provider is the non-broker
[AShareHub API](https://asharehub.com/zh/docs). The deterministic local CSV
provider remains available for development, tests, and offline fallback.

### AShareHub

Create an API key in the AShareHub console, then expose it only through the
environment. Never commit the key:

```powershell
$env:AQR_ASHAREHUB_API_KEY = "your-api-key"
```

Import one stock for a bounded date range:

```powershell
python -m scanner ingest-asharehub --start-date 2026-06-12 --end-date 2026-06-12 --ts-code 000001.SZ
```

Omit `--ts-code` to import the complete Shanghai, Shenzhen, and Beijing market:

```powershell
python -m scanner ingest-asharehub --start-date 2026-06-12 --end-date 2026-06-12 --max-requests 20
```

Repeat `--ts-code` to import multiple selected stocks. Supported suffixes are
`.SH`, `.SZ`, and `.BJ`.

The command:

- Fetches stock metadata and unadjusted daily OHLCV data.
- Paginates up to 5,000 rows per request.
- Stops before exceeding `--max-requests`, which defaults to `20`.
- Converts AShareHub volume from lots to shares.
- Converts AShareHub amount from CNY thousands to CNY.
- Stores the source as `asharehub_raw`.
- Validates the complete response before one transactional upsert.
- Skips a price with a structured warning if the provider temporarily returns
  it before the matching stock metadata becomes available.

AShareHub currently documents a free-plan allowance of 100 requests per day.
Check its current pricing and data-use terms before production or redistribution
use. A `429` response is reported without retrying or partially importing data.

Run the provider through Docker Compose:

```powershell
$env:AQR_ASHAREHUB_API_KEY = "your-api-key"
docker compose -f deployment/compose.yaml --profile tools run --rm scanner ingest-asharehub --start-date 2026-06-12 --end-date 2026-06-12 --max-requests 20
```

### Local CSV

Import the documented synthetic sample after applying migrations:

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

## Technical Signal Scanner

Phase 4 provides three deterministic version 1 research signals:

- `moving_average_cross`: the 5-day moving average crosses above or below the
  20-day moving average.
- `recent_breakout`: the evaluated close is strictly above the highest price
  from the previous 20 trading sessions.
- `volume_spike`: evaluated volume is at least 2 times the average volume from
  the previous 20 trading sessions.

Each rule requires 21 daily bars, including the evaluated date. The comparison
windows exclude the evaluated bar where appropriate. Results describe technical
conditions only; they are not buy, sell, or investment recommendations.

## Interactive Market Chart

The dashboard requests up to 1,000 stored daily bars for the selected stock.
The chart provides:

- Daily, weekly, and monthly K-line levels.
- Weekly and monthly OHLCV aggregation from stored daily records.
- MA5, MA10, MA20, MA30, and MA60 overlays.
- Dashed horizontal and vertical crosshairs on hover.
- Hovered-date OHLC, percentage change, volume, and moving-average values.
- A visible warning when the stored history is too short for longer indicators.

The current database contract contains daily data only. `1W` and `1M` are
transparent aggregations of those daily records; minute and other intraday
levels are not displayed because the platform has no intraday source or schema.

If a chart contains only one candle, inspect the stored history and import a
larger date range:

```powershell
python -m scanner ingest-asharehub --start-date 2025-01-01 --end-date 2026-06-12 --ts-code 002130.SZ --max-requests 5
```

Use dates appropriate to the selected stock and available provider quota.

After importing sufficient history, scan all active and suspended stocks:

```powershell
python -m scanner scan --data-date 2026-06-12
```

Scan selected stocks and signals:

```powershell
python -m scanner scan `
  --data-date 2026-06-12 `
  --stock 000001.SZ `
  --stock 600519.SH `
  --signal moving_average_cross `
  --signal volume_spike `
  --universe-name selected_research_sample
```

Omit `--stock` to use the default A-share universe. Omit `--signal` to evaluate
all three rules. Stock suffixes `.SH`, `.SZ`, and `.BJ` map to the persisted
`SSE`, `SZSE`, and `BSE` exchanges.

The command creates a `scanner_runs` record before evaluation. Successful
matches are stored in `technical_signals` with their versioned definition,
calculated values, and neutral explanation. Missing evaluated-date data or
fewer than 21 bars increments the warning count and does not create a match.
Unexpected failures roll back signal writes and leave the run marked `failed`.

Run the scanner through Docker Compose:

```powershell
docker compose -f deployment/compose.yaml --profile tools run --rm scanner `
  scan --data-date 2026-06-12 --stock 000001.SZ
```

## Backend API

Start PostgreSQL, apply migrations, and run FastAPI:

```powershell
docker compose -f deployment/compose.yaml up -d postgres
alembic upgrade head
uvicorn backend.app.main:app --reload
```

Interactive OpenAPI documentation is available at
`http://localhost:8000/docs`. Canonical resources use `/api/v1`; the same
implemented read resources also have hidden unversioned aliases for local
compatibility.

Check liveness and database readiness:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/api/v1/health
```

List active stocks with pagination:

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/stocks?query=600519&limit=20&offset=0"
```

Get stock details and daily prices:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/stocks/600519.SH
Invoke-RestMethod "http://localhost:8000/api/v1/stocks/600519/prices?exchange=SSE&limit=250"
```

Synchronize only missing daily records for a bounded period:

```powershell
$body = '{"from_date":"2024-06-15","to_date":"2026-06-15"}'
Invoke-RestMethod -Method Post -ContentType "application/json" -Body $body "http://localhost:8000/api/v1/stocks/600519/prices/sync?exchange=SSE"
```

List scanner runs and detected signals:

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/scanner-runs?limit=20"
Invoke-RestMethod "http://localhost:8000/api/v1/signals?signal_code=volume_spike&limit=20"
Invoke-RestMethod "http://localhost:8000/api/v1/stocks/600519/signals?exchange=SSE"
```

Collection endpoints return `items` and `pagination` with `limit`, `offset`, and
`total`. Errors include a stable code and request ID. This API exposes historical
research data, optional generated notes, and local document retrieval; it has no
authentication in the local MVP and contains no broker, order, execution, or
agent endpoints.

Browser access is restricted to origins in `AQR_CORS_ORIGINS`, represented as a
JSON array. The default allows only `http://localhost:5173`.

## AI Research Notes

Research-note generation is disabled by default. Configure an
OpenAI-compatible service in `.env`:

```dotenv
AQR_AI_PROVIDER=openai_compatible
AQR_AI_BASE_URL=https://api.openai.com/v1
AQR_AI_API_KEY=replace_with_a_local_secret
AQR_AI_MODEL=replace_with_a_supported_model
```

Apply the Phase 7 migration and start the backend:

```powershell
alembic upgrade head
uvicorn backend.app.main:app --reload
```

Generate a note from stored context:

```powershell
$body = @{
  price_window = 20
  signal_limit = 20
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/stocks/600519/research-notes?exchange=SSE" `
  -ContentType "application/json" `
  -Body $body
```

Retrieve stored notes:

```powershell
Invoke-RestMethod `
  "http://localhost:8000/api/v1/stocks/600519/research-notes?exchange=SSE"
Invoke-RestMethod `
  "http://localhost:8000/api/v1/research-notes/{note_id}"
```

The backend constructs model input only from stored stock metadata, a bounded
daily-price summary, and stored technical signals. It does not accept a
free-form prompt. Generated output is checked for action-oriented or guaranteed
outcome language before the note is committed. Provider failures do not affect
market ingestion, scanning, dashboard reads, or existing stored notes.

## RAG Knowledge Base

Phase 8 uses the `pgvector` extension in the existing PostgreSQL service.
Documents must be supplied locally; the platform has no paid-report scraper or
remote document downloader.

Supported formats:

- UTF-8 `.txt`
- UTF-8 `.md`
- Text-based `.pdf`

Apply the migration and start the backend:

```powershell
alembic upgrade head
docker compose -f deployment/compose.yaml up --build -d postgres backend
```

Upload a document after confirming that it may be stored and processed:

```powershell
curl.exe -X POST "http://localhost:8000/api/v1/documents" `
  -F "file=@C:\research\annual-report.pdf;type=application/pdf" `
  -F "document_type=annual_report" `
  -F "rights_confirmed=true" `
  -F "stock_id=1"
```

Search indexed chunks:

```powershell
$body = @{
  query = "operating cash flow and revenue observations"
  document_type = "annual_report"
  limit = 10
  minimum_score = 0.0
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/documents/search" `
  -ContentType "application/json" `
  -Body $body
```

The response contains chunk text, similarity scores, document identifiers,
source names, optional stock references, and chunk indexes for citation.
Uploading identical extracted text is idempotent. Deleting a document through
`DELETE /api/v1/documents/{document_id}` removes its chunks.

The default `local_hash` embedding provider is deterministic, offline, and
suited to development and tests. It mainly captures shared terms and character
features; configure an OpenAI-compatible embedding provider for stronger
semantic retrieval:

```dotenv
AQR_RAG_EMBEDDING_PROVIDER=openai_compatible
AQR_RAG_EMBEDDING_BASE_URL=https://api.openai.com/v1
AQR_RAG_EMBEDDING_API_KEY=replace_with_a_local_secret
AQR_RAG_EMBEDDING_MODEL=replace_with_a_supported_embedding_model
```

The database schema uses fixed 256-dimensional vectors. The configured provider
must support 256-dimensional output. Search compares only vectors created by
the currently configured embedding model. Delete and re-upload documents, or
run a future re-embedding migration, before changing models.

### Full MVP with Docker Compose

Build and start PostgreSQL, the backend, and the frontend:

```powershell
docker compose -f deployment/compose.yaml up --build -d
```

Open:

- Dashboard: `http://localhost:5173`
- API documentation: `http://localhost:8000/docs`

Import sufficient market history and run the scanner through the documented
one-shot scanner commands to populate charts and technical signals.

### PostgreSQL Integration Test

The default test suite validates models, AShareHub and CSV parsing, signal
calculations, CLI behavior, constraints, relationships, and offline migration
SQL without requiring a running database.

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
idempotent CSV imports, scanner lifecycle and persistence, transaction rollback,
and then downgrade back to an empty schema.

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
- `AQR_CORS_ORIGINS`
- `AQR_ASHAREHUB_API_KEY` (backend and scanner; secret, never commit)
- `AQR_ASHAREHUB_TIMEOUT_SECONDS`
- `AQR_ASHAREHUB_SYNC_MAX_REQUESTS`
- `AQR_AI_PROVIDER` (`disabled` or `openai_compatible`)
- `AQR_AI_BASE_URL`
- `AQR_AI_API_KEY` (backend only; secret, never commit)
- `AQR_AI_MODEL`
- `AQR_AI_TIMEOUT_SECONDS`
- `AQR_AI_MAX_ATTEMPTS`
- `AQR_AI_MAX_OUTPUT_CHARACTERS`
- `AQR_AI_MAX_OUTPUT_TOKENS`
- `AQR_RAG_EMBEDDING_PROVIDER` (`local_hash` or `openai_compatible`)
- `AQR_RAG_EMBEDDING_BASE_URL`
- `AQR_RAG_EMBEDDING_API_KEY` (backend only; secret, never commit)
- `AQR_RAG_EMBEDDING_MODEL`
- `AQR_RAG_EMBEDDING_DIMENSIONS` (must remain `256` for this schema version)
- `AQR_RAG_EMBEDDING_TIMEOUT_SECONDS`
- `AQR_RAG_EMBEDDING_MAX_ATTEMPTS`
- `AQR_RAG_CHUNK_SIZE`
- `AQR_RAG_CHUNK_OVERLAP`
- `AQR_RAG_MAX_DOCUMENT_BYTES`
