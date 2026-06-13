# AI Quant Research Platform

An AI-powered quantitative research platform for educational and research use.
The MVP will support A-share daily market data, deterministic technical signal
scanning, persisted research results, and a web dashboard.

This project does not connect to brokers, execute trades, or provide investment
recommendations.

## Current Status

Phase 1 establishes the local development environment:

- Minimal FastAPI backend with a liveness endpoint.
- Python scanner command-line shell with no scanning logic.
- React and TypeScript application shell with no dashboard features.
- PostgreSQL, backend, frontend, and scanner Docker Compose definitions.
- Python and frontend formatting, linting, type checking, and test tooling.

Database models begin in Phase 2. Market ingestion and scanning logic are not
implemented yet.

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

Application settings use the `AQR_` environment prefix. Phase 1 settings include:

- `AQR_ENVIRONMENT`
- `AQR_BACKEND_HOST`
- `AQR_BACKEND_PORT`

PostgreSQL values are present for the local container, but application database
integration begins in Phase 2.
