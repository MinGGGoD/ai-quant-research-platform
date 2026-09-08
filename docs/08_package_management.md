# Package Management

## Decision

The migration branch uses one package manager and one authoritative lock file
for each application ecosystem:

| Ecosystem | Tool | Manifest | Lock file |
|---|---|---|---|
| Python | uv 0.12.x | `pyproject.toml` | `uv.lock` |
| Frontend | pnpm 11 | `frontend/package.json` | `frontend/pnpm-lock.yaml` |

`requirements.lock` and `frontend/package-lock.json` are no longer supported.
Do not regenerate them or mix pip/npm installation commands into the documented
project workflow.

## Python Workflow

Install the project, runtime dependencies, and the default development group:

```sh
uv sync --frozen
```

Run project commands without activating `.venv`:

```sh
uv run pytest
uv run ruff check .
uv run mypy ai backend rag scanner
```

Add a runtime or development dependency and refresh `uv.lock`:

```sh
uv add package-name
uv add --dev package-name
```

The supported Python range remains 3.11 through 3.13. Production images install
only runtime dependencies with `uv sync --frozen --no-dev --no-editable`.
NumPy is constrained below 2.5 because the 2.5 type stubs require Python 3.12
syntax while the project's strict mypy configuration deliberately targets the
lowest supported Python version, 3.11.

## Frontend Workflow

Install exact locked dependencies and run scripts from `frontend/`:

```sh
pnpm install --frozen-lockfile
pnpm run dev
pnpm test
```

Add a runtime or development dependency with:

```sh
pnpm add package-name
pnpm add --save-dev package-name
```

The `packageManager` field pins pnpm 11.19.0 for reproducibility. Node.js 22 or
newer remains supported. The project-level `.npmrc` uses the official npm
registry so a developer's global mirror setting cannot silently change the
dependency source.

## Shared Commands

`bash setup.sh` performs both frozen installs. `bash test.sh all` runs Python
formatting, linting, strict type checking, pytest with coverage reporting, and
the complete frontend quality pipeline.

GitHub Actions is not part of Phase 1. CI configuration will be added in Phase
10 after the GraphQL contracts, Testcontainers fixtures, and Playwright flows
are stable enough to define the final job boundaries once.

## Phase 1 Verification

Verification completed on September 8, 2026:

- Repeated frozen installation through `bash setup.sh`: pass.
- Ruff, formatting, and strict mypy checks: pass.
- pytest without PostgreSQL: 95 passed, 20 explicitly skipped, 70% coverage.
- pytest with disposable pgvector PostgreSQL 17: 115 passed, 88% coverage.
- Vitest: 19 passed; Prettier, ESLint, TypeScript, and Vite build: pass.
- Backend, frontend, and scanner Docker images: build successfully.
- Backend import, pnpm version, and scanner CLI container smoke tests: pass.
