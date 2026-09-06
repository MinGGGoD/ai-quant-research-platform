# AI Quant Research Platform

## Pre-Migration Baseline

### 1. Purpose

This document records the verified behavior and measurable frontend output at
the start of the Next.js and GraphQL migration. Later phases should preserve
these workflows unless a documented product or API decision changes them.

Baseline source revision: `cb9962f`

Baseline verification date: 2026-09-06

### 2. Current Architecture

- Frontend: React and TypeScript single-page application built with Vite.
- Frontend data access: typed REST wrappers around the browser Fetch API.
- Backend: FastAPI REST endpoints with Pydantic response models.
- Persistence: synchronous SQLAlchemy 2 sessions, Alembic, psycopg 3, and
  PostgreSQL.
- Flexible data: JSONB for signal parameters, matched evidence, provider
  metadata, and document metadata.
- Retrieval: pgvector-backed document chunks and HNSW cosine-search indexes.
- AI: research-note-specific protocol with an OpenAI-compatible implementation.
- Operations: PostgreSQL, backend, frontend, and scanner services under Docker
  Compose.

### 3. Principal User Workflows

The migration must retain these currently delivered frontend workflows:

1. Search and paginate active stocks by code or name.
2. Select a stock and retain up to six recent stock shortcuts in local browser
   storage.
3. Load daily, 30-minute, and 60-minute K-line and volume data for a bounded date
   range.
4. Inspect chart hover details, moving averages, zoom, and pan interactions.
5. Synchronize missing daily price sessions and distinguish cache hits, fetched
   ranges, warnings, and failures.
6. View stored technical signals and their deterministic matched evidence for a
   selected stock.
7. View recent scanner runs and open a run to inspect parameters, lifecycle
   state, counts, warnings, errors, and matched signals.
8. Filter selected-run signals by stock query and signal code.
9. Recover from loading, empty, backend-error, and retry states on narrow and
   wide screens.

The backend additionally supports research-note generation and retrieval,
approved document ingestion, semantic document search with citations, document
lookup, and deletion. These capabilities do not yet have complete frontend
workflows and may be introduced as new Next.js routes during later phases.

### 4. Frontend Source and Build Baseline

Before migration, the main frontend files have these approximate sizes:

| File | Lines |
|---|---:|
| `frontend/src/App.tsx` | 1,146 |
| `frontend/src/App.css` | 1,079 |
| `frontend/src/api.ts` | 179 |

The Vite production build produces:

| Asset | Raw size | Gzip size |
|---|---:|---:|
| HTML entry | 0.53 kB | 0.33 kB |
| Application CSS | 15.08 kB | 4.02 kB |
| Application JavaScript | 219.77 kB | 68.35 kB |

Hashed asset filenames are intentionally omitted because formatting and later
build-tool versions can change hashes without changing meaningful size.

### 5. Verification Baseline

The Phase 0 verification commands are:

```sh
bash test.sh all
```

and, against a disposable pgvector-enabled PostgreSQL database:

```sh
TEST_DATABASE_URL=postgresql+psycopg://ai_quant:local_development_only@localhost:55432/ai_quant_test \
  bash test.sh python
```

Verified results after Phase 0 repairs:

- Ruff lint and formatting: pass.
- mypy strict type checking: pass.
- pytest without a configured PostgreSQL test database: 95 pass and the 20
  PostgreSQL-specific tests skip explicitly.
- pytest against a disposable `pgvector/pgvector:pg17` database: all 115 pass
  with no skips.
- Prettier, ESLint, and TypeScript checking: pass.
- Vitest component and data tests: 19 tests pass.
- Vite production build: pass and remain comparable to the recorded bundle
  baseline.

### 6. Comparison Rules for Later Phases

- Compare user-visible behavior by workflow, not by retaining the original
  component or REST endpoint structure.
- Record intentional route, API, schema, or visual changes in the relevant
  design document and tests.
- Treat an unexplained loss of an error, loading, empty, accessibility, or
  responsive state as a regression.
- Track large changes in JavaScript and CSS output, but do not require Next.js
  chunks to match Vite's bundling layout.
- Keep tests deterministic and independent of live market-data, broker, paid
  LLM, and uncontrolled document sources.
