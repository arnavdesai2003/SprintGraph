# SprintGraph implementation plan and phase acceptance

| Phase | Scope | Current acceptance |
| --- | --- | --- |
| 1 | Repository, application scaffolds, Docker, health checks, setup docs | Complete: application foundation verified and Git initialized in the user terminal. |
| 2 | Schemas, migrations, seed fixtures, verified ingestion, persistence, deduplication | Complete: schemas, seed, ingestion and deduplication verified; all 51 PostgreSQL tests and Ruff passed. |
| 3 | Typed executable LangGraph and four workflows | Complete: 77 PostgreSQL tests, Ruff, rebuilt demo and deployed end-to-end verification passed. |
| 4 | Demo/live GitHub and Jira adapters | Complete for local MVP: 99 tests plus 12 subtests, Ruff, rebuilt demo verification and read-only adapter check passed. Live GitHub/Jira connectivity and read-only PR/sprint workflows verified; one Gemini PR analysis and browser display also passed. |
| 5 | Authentication, RBAC, audit logs and API-backed dashboard | Complete for local MVP: 136 PostgreSQL tests plus 24 subtests, Ruff, frontend build/typecheck/lint and read-only live browser acceptance passed. Production identity hardening remains separate. |
| 6 | Tests, CI, observability and evaluation | 99 PostgreSQL backend tests plus 12 subtests, four browser tests, Ruff and measured 400-event synthetic run passed. CI itself has not run. |

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

## Phase 4 local acceptance complete
User-run suite passed 99 tests and 12 subtests in 7.97s, with clean Ruff. Rebuilt services passed all nine demo verification checks; events 428–432 succeeded on their first attempt. The read-only adapter check retrieved PR 42 (two files, one commit) and four sprint issues with zero LLM calls. Live adapters are validated using mocked HTTP; real-provider connectivity requires separately configured credentials and resources.

## Current increment: real-data LangGraph acceptance
Implement live integrations with demo inference, observed node audits and disabled real inference. Validate actual API/worker/PostgreSQL/dashboard results for project 2, PR 2 and sprint 3 without external mutations or database reset. Real workflow acceptance passed for events 433–435 and the live browser test passed in 675ms. Updated full backend regression-suite/Ruff acceptance remains pending its separate result. Real inference remains disabled.

## Phase 5 active increment
Require exp/sub claims and valid positive user subjects, reject unknown database roles, audit successful login without credential data, verify role revocation and organization isolation, and provide safe dashboard errors for non-JSON API failures. Existing six dashboard pages and RBAC remain in place. Increment complete: agent-run isolated PostgreSQL suite (136 tests and 24 subtests), Ruff, production build, typecheck, ESLint and read-only browser regression passed. No real inference or provider mutation is needed for validation.

## Phase 6 local acceptance
Complete for local MVP: 137 PostgreSQL tests plus 24 subtests, Ruff, four isolated demo browser tests and controlled 400-event synthetic evaluation passed. Dashboard/evaluation metrics agree. CI uses PostgreSQL explicitly; remote Actions execution remains unverified until changes are pushed and its run is inspected. Reproduce isolated demo validation with infra/compose.demo-test.yaml; do not evaluate the live deployment.
