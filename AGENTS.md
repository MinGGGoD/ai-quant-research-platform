# AGENTS.md

## Project Mission

Build an AI-powered quantitative research platform for A-share market analysis,
technical signal research, AI-generated reports, document retrieval, and data
exploration. The platform is strictly for research and education.

## Tech Stack

- Backend: Python, FastAPI
- Database: PostgreSQL, SQLAlchemy
- Frontend: React, TypeScript
- AI: OpenAI-compatible LLM interface; LangGraph may be added later
- RAG: Embeddings and a vector database may be added later
- Deployment: Docker Compose

## Development Rules

- Before coding, provide a short implementation plan.
- Prefer simple, maintainable architecture over premature optimization.
- Keep changes scoped to the requested subsystem; do not modify unrelated code.
- Follow existing component boundaries and established project patterns.
- Do not introduce business logic until its requirements and design are documented.
- Never commit secrets, credentials, generated datasets, or sensitive user data.

## Coding Style

- Write clear, typed, modular code with descriptive names.
- Keep functions and components focused on one responsibility.
- Prefer explicit interfaces and structured data over implicit conventions.
- Add comments only where intent or constraints are not self-evident.
- Use the repository's configured formatters, linters, and static analysis tools.

## Testing Requirements

- Every code change must include or update tests when appropriate.
- Cover success paths, relevant edge cases, and failure behavior.
- Keep tests deterministic and independent of live brokers, paid services, and
  uncontrolled external data.
- Run the relevant test and quality checks before considering work complete.

## Documentation Requirements

- Every new feature must update the relevant files in `docs/`.
- Update API, database, system design, and roadmap documents when their
  contracts or architecture change.
- Keep `README.md` and examples aligned with actual supported behavior.

## Safety and Finance Boundaries

- This platform is for research and education only.
- Do not implement real-money trading execution.
- Do not connect to broker APIs.
- Do not make or present investment recommendations.
- Label generated analysis as informational research, not financial advice.
- Use simulated or historical data for strategy evaluation and demonstrations.
