# Next.js Frontend Architecture

## Purpose

Phase 2 replaces the Vite single-page runtime with Next.js App Router while
preserving the existing FastAPI REST workflows. It deliberately does not add
GraphQL, Tailwind CSS, shadcn/ui, or new document and research-note business
logic; those changes belong to later migration phases.

## Route Map

| Public route | App Router file | Responsibility |
| --- | --- | --- |
| `/` | `src/app/(workspace)/page.tsx` | Default dashboard |
| `/stocks/[exchange]/[symbol]` | `src/app/(workspace)/stocks/[exchange]/[symbol]/page.tsx` | Restore a selected stock on direct load or refresh |
| `/scanner-runs/[runId]` | `src/app/(workspace)/scanner-runs/[runId]/page.tsx` | Restore scanner-run detail on direct load or refresh |
| `/documents` | `src/app/(workspace)/documents/page.tsx` | Route shell for the later document UI |
| `/research-notes` | `src/app/(workspace)/research-notes/page.tsx` | Route shell for the later notes UI |

Parentheses make `(workspace)` a route group: it organizes a shared layout but
does not appear in the browser URL.

## Server and Client Components

Files under `src/app/` are Server Components unless they declare otherwise.
The root layout owns metadata and global styles. The workspace layout renders
`SiteShell`, including navigation and the research-only boundary message.

`src/App.tsx` declares `use client` because it owns React state, effects,
browser storage, REST requests, and router transitions. Its rendering is split
into focused stock, chart/signal, scanner-run list, and scanner-run detail
components. `KlineChart.tsx` is explicitly client-side because it handles
pointer, keyboard, zoom, pan, and crosshair state.

Dynamic route `params` are awaited by the server pages. The resulting stock or
run identifier becomes initial state for the client workspace, so a refresh
does not lose the selected research context.

## Backend URL Boundary

- `NEXT_PUBLIC_API_BASE_URL` is visible to browser code and embedded during
  `next build`. It defaults to `http://localhost:8000`.
- `BACKEND_INTERNAL_URL` is server-only and can use Docker's service hostname.
  Compose sets it to `http://backend:8000`.

Never expose `BACKEND_INTERNAL_URL` through a `NEXT_PUBLIC_` variable. A browser
cannot resolve the Compose-only `backend` hostname, and server-only settings may
later contain infrastructure details that should not enter client bundles.

## Local Commands

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm run dev
pnpm run lint
pnpm run typecheck
pnpm test
pnpm run build
pnpm run start
```

The development and production servers use port 3000. Docker builds standalone
Next.js output and runs it as an unprivileged user. The Compose health check
targets the production server rather than a development process.

## Phase 2 Verification

- Prettier, ESLint, and TypeScript: pass
- Vitest and React Testing Library: 21 tests pass
- Next.js production build: pass, with three static application routes and two
  dynamic server-rendered routes
- Existing Python test suite: pass
- Docker Compose: configuration validates; frontend and backend health checks
  pass; every documented frontend route returns a successful response

The API transport is still REST. Strawberry GraphQL and Apollo Client are added
only after their schema and service boundaries are introduced in later phases.
