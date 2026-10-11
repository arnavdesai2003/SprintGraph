# SprintGraph implementation plan and phase acceptance

| Phase | Scope | Current acceptance |
| --- | --- | --- |
| 1 | Repository, application scaffolds, Docker, health checks, setup docs | Complete: application foundation verified and Git initialized in the user terminal. |
| 2 | Schemas, migrations, seed fixtures, verified ingestion, persistence, deduplication | Complete: schemas, seed, ingestion and deduplication verified; all 51 PostgreSQL tests and Ruff passed. |
| 3 | Typed executable LangGraph and four workflows | Complete: 77 PostgreSQL tests, Ruff, rebuilt demo and deployed end-to-end verification passed. |
| 4 | Demo/live GitHub and Jira adapters | Demo adapters verified. Live credentials and provider verification remain external configuration. |
| 5 | Authentication, RBAC, audit logs and API-backed dashboard | Local demo API/browser acceptance passed. Production identity hardening remains separate. |
| 6 | Tests, CI, observability and evaluation | 77 PostgreSQL backend tests, four browser tests, Ruff and measured 400-event synthetic run passed. CI itself has not run. |

Implementation advanced through the phases before this explicit acceptance audit. Do not redo verified code or infer live production verification from demo results. No public deployment, paid infrastructure or external mutations.

## Phase 1 acceptance
Complete. User-run git init succeeded; application scaffolds, PostgreSQL/Compose startup, health checks, tests and setup documentation are verified.

## Phase 2 acceptance
Complete. The dedicated PostgreSQL suite passed **51 tests in 4.52s**, with Ruff clean. Three Alembic configuration deprecation warnings were addressed by adding path_separator=os; a warning-only targeted rerun remains optional follow-up.

## Current Phase 2 increment
- Reject delivery IDs reused for a different project, event type or normalized payload, with a safe HTTP 409 and no leaked event ID.
- Preserve idempotent matching deliveries and exactly one event/audit record even when inserts race.
- Test verified malformed and oversized webhook payload rejection without persistence.
- Verify frozen Alembic upgrade/downgrade/upgrade against models and seed.
- Run the full suite against a separate PostgreSQL test service and randomly named disposable schema; never the demo database.

## Phase 3 acceptance increment
- Validate routing parameters and project context before allowlisted provider calls.
- Validate provider evidence and full structured results, including resource identity and deterministic ranking/blocker consistency.
- Freeze a UTC reference date per execution for due-date and stalled-work calculations.
- Bound whole-workflow execution time and persist safe failure categories, retries and recovery audits.
- Exercise real StateGraph routing, malformed evidence, model execution-field rejection, result tampering, empty sprints, timeouts and interrupted claims.
- Updated PostgreSQL suite and deployed demo verification must pass before this increment is marked complete.

## Phase 3 runtime validation update
User-run isolated PostgreSQL suite passed 77 tests in 6.41s; Ruff passed without diagnostics. The demo stack rebuilt and started, with PostgreSQL/backend healthy and migration exited successfully. The updated deployed verification script remains pending; the existing report covers the earlier baseline.

## Phase 3 complete
The updated deployed verifier passed all nine checks. Events 423–427 succeeded on their first attempt across all four workflows, with persisted dashboard results and completion audits. Together with 77 PostgreSQL tests and clean Ruff, this completes Phase 3 local acceptance. Live-provider acceptance remains Phase 4 work.
