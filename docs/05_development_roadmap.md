# AI Quant Research Platform

## Development Roadmap

### 1. Roadmap Principles

- Phases 1 through 6 deliver the MVP.
- Each phase should be completed and verified before dependent work begins.
- Keep implementation small, typed, testable, and aligned with the existing
  product, system, database, and API documents.
- Update relevant documentation whenever implementation decisions change a
  documented contract.
- Use historical or synthetic market data from non-broker sources.
- Do not add broker connectivity, trading execution, or investment direction.
- Phases 7 through 10 are optional future enhancements and must not become MVP
  dependencies.

## Phase 1: Project Setup and Development Environment

### Goal

Create a consistent local development foundation for Python, React, PostgreSQL,
tests, linting, configuration, and the initial Docker Compose workflow.

### Tasks

- Define supported Python and Node.js versions.
- Initialize the FastAPI backend package without business endpoints.
- Initialize the React and TypeScript frontend application without dashboard
  features.
- Initialize the scanner as an installable or directly runnable Python package.
- Add dependency and lock-file management for Python and frontend packages.
- Configure Python formatting, linting, type checking, and pytest.
- Configure TypeScript checking, frontend linting, formatting, and tests.
- Add `.env.example` files containing safe local defaults and placeholders.
- Add a minimal Docker Compose setup for PostgreSQL and development services.
- Add basic backend and frontend startup checks.
- Document local setup, common commands, and repository conventions.
- Add CI checks if repository automation is in scope for the initial setup.

### Files Likely to Be Changed

- `README.md`
- `backend/`
- `frontend/`
- `scanner/`
- `tests/`
- `deployment/compose.yaml`
- `.gitignore`
- `.env.example`
- Python dependency and tool configuration files
- Frontend package and tool configuration files
- Optional `.github/workflows/`
- Relevant files in `docs/`

### Acceptance Criteria

- A new developer can follow `README.md` to install dependencies.
- Backend, frontend, scanner help, and PostgreSQL can start locally.
- Docker Compose provides a working development baseline.
- Formatting, linting, type checking, and test commands are documented.
- No secrets or machine-specific configuration are committed.
- No market, signal, AI, RAG, or trading business logic is introduced.

### Testing Requirements

- Add a minimal backend import or startup test.
- Add a minimal frontend render test.
- Add a scanner CLI help or startup test.
- Verify linting, formatting, and type-check commands pass.
- Verify Docker Compose configuration parses and PostgreSQL becomes healthy.

## Phase 2: Database Models and Migrations

### Goal

Implement the MVP PostgreSQL schema and a reliable migration workflow based on
`03_database_design.md`.

### Tasks

- Configure SQLAlchemy database connections and session lifecycle.
- Configure a migration tool and create the initial migration.
- Implement models for:
  - `stocks`
  - `daily_prices`
  - `signal_definitions`
  - `scanner_runs`
  - `detected_signals`
- Add documented primary keys, foreign keys, unique constraints, checks, and
  indexes.
- Define shared database enums or validated string values without creating
  unnecessary abstraction.
- Add transaction helpers usable by the backend and scanner.
- Add deterministic database fixtures for development and tests.
- Document migration, rollback, reset, and fixture-loading commands.
- Do not create the future `research_notes` table yet.

### Files Likely to Be Changed

- `backend/` database configuration and model modules
- `backend/` migration configuration and migration files
- `scanner/` database integration modules, if shared access is needed
- `tests/` database fixtures and integration tests
- `deployment/compose.yaml`
- `.env.example`
- `docs/03_database_design.md`
- `README.md`

### Acceptance Criteria

- A clean PostgreSQL database can migrate from zero to the latest schema.
- All MVP tables, constraints, and indexes match the documented design.
- The latest migration can be rolled back in a disposable test database.
- Duplicate daily prices and duplicate detected signals are rejected.
- Foreign-key relationships preserve scan and signal traceability.
- Backend and scanner database access use the same documented schema.

### Testing Requirements

- Test migration upgrade from an empty database.
- Test migration downgrade in an isolated database.
- Test model creation and basic persistence.
- Test unique, foreign-key, check, and nullability constraints.
- Test transaction rollback behavior.
- Run integration tests against PostgreSQL rather than substituting SQLite for
  PostgreSQL-specific behavior.

## Phase 3: Market Data Ingestion

### Goal

Load validated A-share stock metadata and daily OHLCV data into PostgreSQL from
an approved non-broker source or local research dataset.

### Tasks

- Define a small provider-neutral ingestion interface.
- Implement one initial non-broker provider or documented local file importer.
- Import and update stock metadata.
- Import daily OHLCV records using upserts keyed by stock and trade date.
- Validate symbols, exchanges, dates, prices, volume, and OHLC relationships.
- Define and document the source's price-adjustment convention and units.
- Detect duplicate, missing, malformed, and stale records.
- Produce structured ingestion summaries and error logs.
- Add a CLI command for repeatable ingestion.
- Add safe synthetic or clearly labeled sample fixtures.
- Document data-source limitations and acceptable use.

### Files Likely to Be Changed

- `data/`
- `scanner/` ingestion, validation, provider, and CLI modules
- `backend/` shared data models or repositories
- `tests/` ingestion fixtures and tests
- `.env.example`
- `README.md`
- `docs/01_product_requirements.md`
- `docs/02_system_design.md`
- `docs/03_database_design.md`

### Acceptance Criteria

- A documented command imports a sample A-share universe and daily K-line data.
- Re-running the same import does not create duplicate rows.
- Invalid OHLCV data is rejected or reported without silent corruption.
- Imported records include their source and effective trading date.
- Stock charts can be supported by the stored data shape.
- Ingestion has no broker API dependency and does not require real-time data.

### Testing Requirements

- Unit test record parsing and validation.
- Test malformed dates, invalid OHLC relationships, negative values, duplicates,
  and missing required fields.
- Test idempotent upsert behavior against PostgreSQL.
- Test transaction rollback when a batch fails.
- Add a fixture-based integration test from input file to persisted rows.

## Phase 4: Technical Signal Scanner

### Goal

Build the deterministic CLI scanner that evaluates daily market data, records
scan history, and persists explainable technical signal matches.

### Tasks

- Define the scanner CLI inputs and exit codes.
- Implement scan-run lifecycle management.
- Define the initial small set of documented signal rules.
- Implement reusable daily indicator calculations.
- Version each signal definition and persist its parameters.
- Validate sufficient lookback data before evaluating a rule.
- Distinguish valid non-matches from insufficient or invalid data.
- Store detected signals, matched values, and neutral explanations.
- Store run totals, warnings, failures, and timestamps.
- Prevent duplicate results for the same run, stock, signal, and date.
- Add structured logging and concise CLI summaries.
- Keep scanner execution independent from backend and frontend availability.

### Files Likely to Be Changed

- `scanner/` CLI, orchestration, indicators, rules, validation, and persistence
- `backend/` shared database models or repositories
- `tests/` unit, property, fixture, and integration tests
- `data/` deterministic signal fixtures
- `README.md`
- `docs/01_product_requirements.md`
- `docs/02_system_design.md`
- `docs/03_database_design.md`
- `docs/05_development_roadmap.md`

### Acceptance Criteria

- A documented CLI command runs a scan for a selected date, universe, and signal
  set.
- Identical data and configuration produce identical results.
- Each match identifies its stock, run, signal version, date, values, and
  explanation.
- Insufficient data is reported separately from a valid non-match.
- Scanner runs end in a documented terminal state after success or failure.
- The scanner contains no order, portfolio, broker, or recommendation behavior.

### Testing Requirements

- Unit test every indicator and signal around threshold boundaries.
- Test insufficient lookback periods and malformed data.
- Use small hand-calculated fixtures with known matches and non-matches.
- Test scan lifecycle transitions and failure recovery.
- Test result uniqueness and transactional persistence.
- Add an end-to-end scanner test from stored daily prices to stored signals.

## Phase 5: Backend API

### Goal

Implement the FastAPI read API that exposes stocks, daily prices, scanner runs,
and detected signals to the frontend.

### Tasks

- Implement liveness and readiness endpoints.
- Implement versioned `/api/v1` routing.
- Implement stock listing and filtering.
- Implement stock daily-price queries for chart data.
- Implement scanner-run listing and detail endpoints.
- Implement detected-signal listing and stock-signal endpoints.
- Add pagination, deterministic ordering, and date-range validation.
- Define response schemas separate from ORM models.
- Implement the documented common error format and request IDs.
- Configure restricted local-development CORS.
- Keep the optional scan-trigger endpoint disabled unless explicitly required.
- Generate and review the OpenAPI schema.
- Document local API startup and examples.

### Files Likely to Be Changed

- `backend/` FastAPI application, routes, schemas, services, and repositories
- `tests/` API unit and integration tests
- `.env.example`
- `deployment/compose.yaml`
- `README.md`
- `docs/04_api_design.md`
- Other design documents only when contracts change

### Acceptance Criteria

- Every required read endpoint in `04_api_design.md` returns the documented
  response shape.
- Filtering, pagination, ordering, empty results, and errors behave consistently.
- Daily-price responses are suitable for chronological K-line charts.
- Scan details do not embed unbounded signal collections.
- The API starts locally and reports database readiness.
- No authentication is required for isolated local MVP use.
- No trading, broker, account, position, or order endpoint exists.

### Testing Requirements

- Test every endpoint's success, empty, validation, and not-found behavior.
- Test pagination boundaries and deterministic ordering.
- Test database-unavailable readiness behavior.
- Test response schemas against representative fixtures.
- Test CORS configuration for allowed and disallowed origins.
- Add PostgreSQL-backed API integration tests.

## Phase 6: Frontend Dashboard

### Goal

Deliver the complete MVP user experience for viewing scan history, detected
signals, stock details, and daily K-line charts.

### Tasks

- Establish routing, layout, API client, and typed response models.
- Build a dashboard summary and recent scanner-runs view.
- Build scanner-run history and run-detail pages.
- Build a detected-signals table with date, stock, and signal filters.
- Build stock search and stock-detail navigation.
- Build daily candlestick and volume charts.
- Overlay or list detected signal dates for the selected stock.
- Display matched values and deterministic explanations.
- Implement loading, empty, warning, failed, and unavailable states.
- Clearly distinguish market dates from scan execution timestamps.
- Display data-source and price-adjustment context.
- Ensure all wording remains neutral and research-focused.
- Add accessible interaction and responsive baseline styling.
- Document frontend startup and supported workflows.

### Files Likely to Be Changed

- `frontend/` pages, components, hooks, API client, types, styles, and tests
- `tests/` end-to-end or cross-service tests
- `.env.example`
- `deployment/compose.yaml`
- `README.md`
- `docs/01_product_requirements.md`
- `docs/02_system_design.md`
- `docs/04_api_design.md`
- `docs/05_development_roadmap.md`

### Acceptance Criteria

- A user can view scan history and open a scanner-run detail page.
- A user can filter detected signals and inspect matched values.
- A user can search for a stock and view its daily K-line and volume chart.
- Signal dates and explanations can be inspected from the stock view.
- Empty, failed, and completed-with-warning states are understandable.
- The frontend uses only documented backend APIs.
- The full local scan-to-dashboard workflow works through Docker Compose.
- No screen presents trading actions or personalized investment direction.

### Testing Requirements

- Unit test data formatting, filters, and signal display components.
- Component test loading, empty, error, warning, and populated states.
- Test API client error handling and typed response assumptions.
- Test keyboard navigation and basic accessibility.
- Add an end-to-end test covering stock search, scan selection, and signal
  inspection.
- Run a smoke test against the local Docker Compose stack.

### MVP Completion Gate

The MVP is complete only when Phases 1 through 6 satisfy their acceptance
criteria and:

- Historical or synthetic daily A-share data can be ingested.
- The CLI scanner can detect and persist documented technical signals.
- The FastAPI backend can expose stored research data.
- The React dashboard can display scan results and stock charts.
- The stack starts locally through the documented Docker Compose workflow.
- Core paths have automated tests and current documentation.
- There is no broker integration, order execution, or investment-advice
  behavior.

## Phase 7: AI Report Generation

**Future enhancement. Not required for MVP.**

### Goal

Generate neutral, traceable research summaries from stored scan results through
an OpenAI-compatible LLM interface.

### Tasks

- Define report use cases, inputs, output schema, and safety wording.
- Implement a provider-neutral LLM client interface.
- Add prompt templates and explicit prompt versioning.
- Generate reports only from stored, approved research context.
- Persist generated reports using the future `research_notes` design.
- Store model, prompt, parameters, timestamps, and source references.
- Add cost, timeout, retry, and output-size controls.
- Add human review before reports are treated as complete.
- Add evaluation fixtures for factual grounding and prohibited wording.
- Update product, system, database, and API documentation before implementation.

### Files Likely to Be Changed

- `ai/`
- `backend/` report services, schemas, persistence, migrations, and optional APIs
- `frontend/` report display components
- `tests/` AI contract, safety, and integration tests
- `.env.example`
- `README.md`
- `docs/01_product_requirements.md`
- `docs/02_system_design.md`
- `docs/03_database_design.md`
- `docs/04_api_design.md`
- `docs/05_development_roadmap.md`

### Acceptance Criteria

- Reports cite the stored scan results and context used to generate them.
- Provider configuration can change without changing report-domain logic.
- Generated content is labeled informational and does not recommend actions.
- Failures, timeouts, and invalid structured output are handled visibly.
- The core scanner and dashboard remain usable when the AI service is disabled.

### Testing Requirements

- Unit test prompt construction and structured-output validation.
- Use fake LLM clients for deterministic tests.
- Test timeout, retry, malformed response, and provider-error behavior.
- Evaluate grounding against fixed scan-result fixtures.
- Test for prohibited recommendation, guarantee, and execution language.
- Keep live-provider tests optional and excluded from default CI.

## Phase 8: RAG Knowledge Base

**Future enhancement. Not required for MVP.**

### Goal

Add grounded retrieval over approved research notes, filings, announcements, and
educational documents.

### Tasks

- Define supported document types, provenance, retention, and access rules.
- Implement ingestion, text extraction, normalization, and chunking.
- Define provider-neutral embedding interfaces.
- Select a vector database only after evaluating local requirements.
- Store document and chunk metadata with source lineage.
- Implement retrieval, filtering, ranking, and citation assembly.
- Connect retrieved context to AI reports without coupling it to the scanner.
- Add document update and deletion workflows.
- Build retrieval-quality evaluation datasets.
- Update architecture, database, API, and safety documentation.

### Files Likely to Be Changed

- `rag/`
- `ai/`
- `backend/` document and retrieval APIs
- `frontend/` document and citation views
- `data/` non-sensitive evaluation documents
- `deployment/` vector-store service configuration
- `tests/` ingestion and retrieval tests
- `.env.example`
- `README.md`
- Relevant files in `docs/`

### Acceptance Criteria

- Approved documents can be ingested with traceable source metadata.
- Retrieval returns relevant chunks with citations.
- Re-ingestion is idempotent or produces documented versions.
- Deleted documents no longer appear in retrieval results.
- AI output clearly distinguishes retrieved facts from generated synthesis.
- RAG services remain optional and do not affect MVP scanning availability.

### Testing Requirements

- Unit test extraction, chunking, metadata, and deduplication.
- Test embedding and vector-store adapters with deterministic fakes.
- Test document update and deletion behavior.
- Evaluate recall and citation accuracy against a fixed dataset.
- Test unsupported, empty, malformed, and oversized documents.
- Keep external embedding-provider tests optional.

## Phase 9: LangGraph Multi-Agent Workflow

**Future enhancement. Not required for MVP.**

### Goal

Add bounded, observable research workflows only where multiple explicit steps
provide value beyond ordinary application services.

### Tasks

- Identify validated workflows that require orchestration.
- Define narrow agent roles, state, inputs, outputs, and stop conditions.
- Implement LangGraph state transitions and checkpointing.
- Restrict tools to read-only research capabilities by default.
- Add human approval before publishing or persisting important outputs.
- Add iteration, token, cost, and execution-time limits.
- Record tool calls, source references, model versions, and workflow status.
- Implement cancellation, retry, and partial-failure behavior.
- Prevent access to brokers, orders, credentials, or unrestricted system tools.
- Document threat models, prompt-injection handling, and audit expectations.

### Files Likely to Be Changed

- `ai/` graph definitions, agents, tools, policies, and state models
- `rag/` retrieval tools
- `backend/` workflow APIs and persistence
- `frontend/` workflow status and review interfaces
- `tests/` graph, policy, and adversarial tests
- `deployment/` optional worker configuration
- `README.md`
- Relevant files in `docs/`

### Acceptance Criteria

- Every workflow has explicit entry, terminal, failure, and cancellation states.
- Tool access is allowlisted and bounded.
- Human review is required for final generated research artifacts.
- Runs are auditable through stored state and source references.
- Agent failures cannot corrupt market data or scanner history.
- No agent can execute trades, connect to brokers, or issue personalized
  investment direction.

### Testing Requirements

- Unit test graph transitions and stop conditions.
- Test tool permission enforcement and human-review gates.
- Test retries, cancellation, timeouts, and partial failures.
- Use deterministic model and tool fakes in default tests.
- Add prompt-injection and malicious-document test cases.
- Test token, iteration, and cost limits.

## Phase 10: Docker Deployment and Polish

**Future enhancement. Not required for MVP.**

### Goal

Harden the existing local Docker Compose baseline, improve operability, and
polish the complete research platform after future modules are validated.

### Tasks

- Create optimized multi-stage images for required services.
- Separate development and packaged local deployment configurations.
- Add health checks, dependency conditions, restart policies, and resource
  guidance.
- Provide explicit migration and one-shot scanner commands.
- Add persistent volume, backup, restore, and reset documentation.
- Add optional AI, RAG, vector-store, and workflow profiles.
- Review configuration, secrets handling, logs, and startup diagnostics.
- Improve frontend performance, accessibility, and error recovery.
- Add release versioning and change-log practices.
- Add smoke-test and release-check automation.
- Review all documentation for consistency with delivered behavior.
- Perform a final safety audit for prohibited finance capabilities and wording.

### Files Likely to Be Changed

- `deployment/`
- Service Dockerfiles in `backend/`, `frontend/`, `scanner/`, `ai/`, and `rag/`
- `.env.example`
- `.dockerignore`
- CI or release workflow files
- `README.md`
- `tests/` smoke and deployment tests
- All relevant files in `docs/`

### Acceptance Criteria

- A documented command starts the selected local service profile.
- Required services report healthy and recover predictably from restarts.
- Database data persists across container recreation.
- Migration, scan, backup, restore, and shutdown procedures are documented.
- Optional future services can be disabled without breaking the MVP.
- No secret is embedded in an image or committed configuration.
- Release documentation accurately describes supported and unsupported
  capabilities.

### Testing Requirements

- Validate Docker Compose configuration for each supported profile.
- Build all service images from a clean environment.
- Run health and smoke tests against the packaged stack.
- Test database persistence, backup, and restore with non-sensitive fixtures.
- Test migration execution during release preparation.
- Run backend, scanner, frontend, AI, RAG, and workflow test suites as
  applicable.
- Complete a manual safety and documentation review before release.

## 2. Phase Dependencies

| Phase | Depends On | Delivery Status |
|---|---|---|
| 1. Setup | None | MVP |
| 2. Database | Phase 1 | MVP |
| 3. Ingestion | Phases 1-2 | MVP |
| 4. Scanner | Phases 1-3 | MVP |
| 5. Backend API | Phases 1-4 | MVP |
| 6. Frontend | Phases 1-5 | MVP completion |
| 7. AI reports | Stable Phase 6 | Future |
| 8. RAG | Stable Phase 6; Phase 7 integration optional | Future |
| 9. LangGraph | Validated Phase 7 and/or 8 use cases | Future |
| 10. Deployment polish | Delivered modules from preceding phases | Future |

Phases may overlap only when their contracts are stable and the overlap does not
create undocumented coupling.
