# ADR 0001: Adopt Next.js and GraphQL Through Incremental Migration

- Status: Accepted
- Date: 2026-09-06
- Decision owners: Project maintainers
- Related plan: `docs/06_stack_migration_plan.md`

## Context

The current application is a working local research platform built with a
React/Vite frontend, a FastAPI REST backend, SQLAlchemy, and PostgreSQL. REST and
Vite remain sufficient for the delivered MVP, but the next development goal is
also educational: the repository should demonstrate practical, explainable use
of a modern full-stack TypeScript, GraphQL, and PostgreSQL toolchain for
portfolio and employment purposes.

A complete rewrite would combine frontend framework migration, API contract
migration, database access changes, and UI redesign in one high-risk change. It
would also make regressions difficult to attribute. Keeping both architectures
permanently would instead create duplicate contracts and maintenance work.

## Decision

The project will migrate incrementally to the following target architecture:

- Next.js App Router, React, and TypeScript for the frontend.
- Tailwind CSS and shadcn/ui for the shared UI system.
- React Hook Form and Zod for meaningful user-input workflows.
- Apollo Client and GraphQL Code Generator for typed application operations.
- FastAPI with Strawberry GraphQL for application queries and mutations.
- Pydantic for settings, service-boundary validation, and structured LLM output.
- SQLAlchemy 2, Alembic, psycopg 3, and PostgreSQL for persistence.

Migration will proceed as end-to-end vertical slices. The existing REST client
and endpoints remain available until a replacement slice has backend,
frontend, integration, and end-to-end coverage.

The long-term transport boundary is intentionally hybrid:

- GraphQL owns normal application reads and mutations.
- REST retains liveness, readiness, file upload/download, and operational
  endpoints where GraphQL provides no material benefit.
- Both transports call shared application services; neither transport calls the
  other's handlers.

Strawberry types will describe the public GraphQL schema explicitly. Pydantic
models will not be exposed automatically with broad field inclusion because API
exposure and runtime validation are separate responsibilities.

GraphQL resolvers must not run blocking database or provider I/O directly on the
event loop. The detailed SQLAlchemy async-session transition will be decided
and documented before database-backed GraphQL fields are implemented. The
scanner CLI may retain synchronous database sessions.

The RAG feature remains optional at runtime, but pgvector is part of the current
development database image and schema. Making the PostgreSQL extension itself
optional is not part of this migration.

## Consequences

### Positive

- Each target technology supports an implemented workflow rather than existing
  only as an installed dependency.
- The application remains usable and testable throughout the migration.
- Generated GraphQL operation types replace manually duplicated frontend
  response types over time.
- Shared services protect domain rules from transport-specific duplication.
- The final repository can demonstrate framework choices, API design, caching,
  validation, database behavior, and testing tradeoffs.

### Costs and Risks

- REST and GraphQL coexist temporarily, requiring parity tests during cutover.
- Next.js introduces server/client component and deployment boundaries that do
  not exist in the current Vite SPA.
- GraphQL requires explicit pagination, query-cost controls, error handling,
  batching, and Apollo cache policies.
- The migration is longer than a direct rewrite and requires disciplined
  removal of transitional code.

### Risk Controls

- Complete and verify one vertical slice before starting the next.
- Export and version a deterministic GraphQL schema for code generation.
- Add bounded query and date-range limits before exposing market-data fields.
- Add query-count tests and DataLoaders for nested GraphQL relationships.
- Keep file upload on REST unless a separate security decision changes it.
- Remove superseded REST and Vite code in the final cutover phase.

## Alternatives Considered

### Keep Vite and REST Permanently

This is the smallest production architecture for the current MVP, but it does
not meet the explicit learning objective for Next.js, GraphQL, Apollo Client,
and GraphQL Code Generator.

### Rewrite the Entire Application at Once

This would reach the target stack faster in calendar steps, but it would remove
the working comparison baseline and combine too many failure sources. It is
rejected in favor of independently testable migrations.

### Use GraphQL for Every Endpoint

This would create uniform transport at the cost of forcing file transfer and
operational health checks into GraphQL. The project prefers a small, documented
REST surface for those cases.

### Automatically Derive the GraphQL API From ORM or Pydantic Models

This would reduce initial type declarations but couple database, validation,
and public API schemas. Explicit GraphQL types are preferred so that fields are
exposed intentionally and can evolve independently.
