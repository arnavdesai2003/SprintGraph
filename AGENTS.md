# SprintGraph
Backend: Python 3.12+, FastAPI, SQLAlchemy, Alembic, LangGraph. Frontend: Next.js App Router, TypeScript, Tailwind, TanStack Query, Recharts.
Run `docker compose up --build -d`, `docker compose exec backend pytest`, `docker compose exec backend ruff check .`, and frontend checks via `docker build --target build -t sprintgraph-frontend-check frontend` then `docker run --rm sprintgraph-frontend-check npm run typecheck` and `npm run lint` in that image. The frontend runtime image has no source/dev dependencies.
Use typed validated inputs, organization-scoped queries, deterministic routing, advisory AI results, and environment secrets. External writes require server-side authorization and approval; currently adapters are read-only.
Update PROGRESS.md and docs/architecture.md after milestones. Never claim unmeasured results. Tests must cover security, ingestion, routing and provider failures.

Browser acceptance: `docker compose --profile demo --profile test run --build --rm e2e` after rebuilding frontend. Reports in artifacts/e2e. Use real services; do not enable credential-bearing browser traces.
