# SprintGraph progress

## Current status
The local demo MVP acceptance checks are complete: healthy Docker services, migrations and seeding, development authentication/RBAC, verified ingestion, all four LangGraph workflows, persisted dashboard results, audit records, 77 PostgreSQL backend tests, frontend build/typecheck, and four real-service browser tests passed. ESLint passed with zero errors; its two configuration warnings were corrected in source. Dependency snapshots were captured and validated through locked rebuilds. A 400-event synthetic demo evaluation completed successfully; observed measurements are documented in docs/evaluation.md.

## Implemented
- Modular FastAPI/Next.js monorepo, health/readiness endpoints, Docker images and Compose with PostgreSQL, migrations, seed, API, worker and frontend services.
- Eleven SQLAlchemy tables and a frozen Alembic migration. Private generated local environment values and idempotent demo seed.
- Verified GitHub HMAC and shared-secret Jira ingestion, delivery deduplication, bounded payload validation and durable event storage.
- Typed executable LangGraph classification, deterministic routing, four specialized workflows, Pydantic outputs, persisted execution attempts and results.
- Database-backed asynchronous worker, bounded exponential retries, stale-claim recovery, safe errors and audit records.
- Demo and live read-only GitHub/Jira adapters; configurable OpenAI-compatible structured analysis. No external mutation tools.
- Development authentication, backend RBAC and organization authorization, confirmed role changes and local provisioning CLI.
- Six API-connected dashboard pages using TanStack Query, Recharts, Tailwind and Radix/shadcn-style components.
- Automated tests, CI, synthetic evaluation tooling, signed demo submission and end-to-end verification scripts, setup and architecture documentation.

## Verified results
- User-provided Compose output: PostgreSQL/backend/frontend healthy, worker running, migrate and seed exited 0. Next.js 15.5.27 ready; API readiness returned 200.
- User-provided PostgreSQL query: events 1–9 succeeded, each on its first attempt, no error. All four workflow types represented.
- User-run `docker compose exec -T backend pytest -q`: **31 passed in 2.19s**.
- User-run `docker compose exec -T backend ruff check .`: **All checks passed**.
- User-run `python3 scripts/verify_demo.py`: **passed**. Events 10–14 transitioned pending to succeeded on their first attempts. Persisted results were available through dashboard APIs; workflow completion was audited.
- Directly inspected verification-report.json: nine acceptance checks, demo mode, events 10–14, no credentials.
- Earlier offline checks: eight scoring/blocker and three signature unit tests; real SQLAlchemy persistence/deduplication checks; demo adapter and safe mocked provider error checks; Python compilation; TypeScript syntax parsing/transpilation; Compose configuration parsing.

## Environment history
The authoring session cannot access the Docker socket or make local HTTP requests. Initial dependency downloads and Git initialization were blocked. User terminal execution enabled Docker build/startup and runtime verification. No public deployment, paid infrastructure or external mutation occurred.

## Next hardening work
Dependency locks are now captured. Frontend/backend locked rebuilds passed; the browser lock was captured but its npm-ci rebuild has not yet been separately verified. A standalone zero-warning lint rerun has not been supplied after the two small config fixes; the subsequent frontend/browser rebuild succeeded. Run the synthetic evaluation only when measuring demo performance. Live providers and organizational production authentication require separate configuration and validation.


## Known limitations
Local authentication requires organizational OIDC/session hardening before production. Single-worker recovery lacks heartbeat/fencing and node checkpointing. Provider retry windows do not honor Retry-After/reset headers. Live Jira custom status/severity mapping needs installation-specific configuration. No project provisioning UI exists yet. Browser E2E coverage passed locally; CI execution is not yet verified. Historical 41% automation across 537+ events remains unverified.

## Frontend validation milestone
- User-run Docker build-stage image build succeeded.
- User-run `npm run typecheck`: passed with no diagnostics.
- User-run `npm run lint`: zero errors, two import/no-anonymous-default-export warnings in eslint.config.mjs and postcss.config.mjs.
- Changed both configuration modules to export named local config variables. This preserves configuration behavior; a lint rerun against the corrected files is pending.
- Browser interaction acceptance and dependency lockfile generation remain outstanding.

## Browser automation implementation
- Added an optional Playwright test runner and four real-service browser tests: six-page navigation/evidence, PR regeneration and persisted activity, Developer UI/backend restrictions, canceled role confirmation and sign-out.
- Added an accessible Sign out label and an optional Compose test profile. Browser credentials are not traced or logged; reports/screenshots are local Git-ignored artifacts.
- Compose test-profile configuration parses. Browser execution is still pending because this session cannot access Docker or download dependencies.
- Frontend Docker builds now use npm ci when a package-lock.json is available, with npm install only during initial unlocked bootstrap. Lockfile extraction instructions added to README.

## Local MVP acceptance completed
- User-run Playwright suite: **4 passed in 6.6s** against actual Docker services.
- Verified six-page Admin navigation and source evidence, blocker certainty labels, browser PR regeneration through persisted successful execution, Developer UI/backend restrictions, canceled role confirmation, sign-out and no uncaught page errors in the navigation test.
- Directly inspected artifacts/e2e/test-results/.last-run.json: status passed, failedTests empty. HTML report and overview screenshot are present.
- This completes the defined local demo acceptance checks. Live-provider verification, public deployment, organizational authentication, and historical resume metrics are not included in this result.

## Reproducibility and evaluation hardening (implementation pending container validation)
- Added capture_locks.py to extract validated image dependencies, verify manifest agreement and reject credential-bearing/direct URLs before writing files. No lock contents fabricated; capture has not run here.
- Backend Docker/CI now consume a requirements snapshot when present and run pip check. Frontend/browser builds already consume npm locks when present. CI frontend lint now fails on warnings.
- Evaluation now filters queue claims to its batch, counts successful automated events correctly, refuses live/paid model providers, records code hashes/config/runtime, and fails its CLI when events fail.
- Added metrics unit tests and evaluation integration tests, including preservation of unrelated seeded queue rows. Six new metric tests passed offline. Full updated pytest/Ruff need Docker validation.
- Added run_evaluation.py to pause/restart the existing worker safely and save the measured demo report. No performance result is claimed before that script runs.

## Reproducibility and measured evaluation verified
- Captured frontend/package-lock.json, e2e/package-lock.json and backend/requirements.lock from existing tested images. Direct inspection confirms manifest agreement and pinned Python packages.
- User-run locked frontend/backend Docker rebuild succeeded, including npm ci and backend pip check. Browser lock capture succeeded; its separate locked rebuild is not claimed.
- Updated backend suite: **42 passed in 2.82s**. Ruff: **All checks passed**.
- Evaluation: **400/400 succeeded**, zero failures/unfinished, 400 attempts, 100 events per workflow. Wall duration 2.564605209 seconds; throughput 155.969425078 events/second; P50 1264.806 ms and P95 2240.853 ms.
- Confirmed saved report contents and all four source hashes directly against workspace files. Python 3.12.15, Linux aarch64, deterministic demo LLM; no production/provider-performance or historical productivity claim.
- Worker stopped before evaluation and started successfully afterward, as shown in user terminal output.

## Explicit Phase 1/2 acceptance audit
- Phase 1 application foundation is verified by existing Docker startup, health, backend and frontend build/test evidence. Git initialization is still pending: a fresh attempt was denied by the sandbox. Do not mark that item complete until normal-terminal git init succeeds.
- Phase 2 database/ingestion baseline already passed local acceptance. Added collision-safe delivery deduplication: reused IDs with different project/type/payload return 409 rather than disclose or reuse the wrong event.
- Added malformed/oversized signed-payload and generated-ID tests, an Alembic upgrade/downgrade/upgrade roundtrip test, and a synchronized PostgreSQL concurrent-insert test checking one event and one audit record.
- Added optional database-test Compose profile with a dedicated sprintgraph_test database. Tests use a generated schema and refuse non-test PostgreSQL database names. CI runs this isolated suite after generating its private test environment.
- Python compilation and Compose database-test configuration parse passed. New runtime tests remain pending; no updated test count or Phase 2 completion is claimed.

## Phases 1 and 2 complete
- User-run git init initialized the workspace repository; directly confirmed Git now recognizes the workspace. No commit or remote publication was performed.
- Dedicated PostgreSQL container suite: **51 passed in 4.52s**. This includes synchronized concurrent duplicate inserts, safe delivery collision rejection, malformed/oversized payload rejection, generated delivery IDs and Alembic upgrade/downgrade/upgrade with schema/seed verification.
- Ruff: **All checks passed**.
- Three Alembic configuration DeprecationWarnings reported the missing path_separator setting. Added path_separator=os to address the warning without changing the schema. A warning-free rerun is not yet claimed.
- Phase 1 foundation and Phase 2 database/ingestion acceptance are complete. Later-phase implementations already exist and have demo validation; they should be audited incrementally rather than recreated.

## Phase 3 implementation increment (container validation pending)
- Added typed Pydantic project context, tool parameters, provider evidence and complete result schemas for all four workflows. Unexpected model fields are rejected.
- Validated requested and returned PR identity, project-scoped Jira issues and unique issue keys before analysis. UTC reference dates are captured once per execution.
- Final validation verifies source evidence, sprint metrics, priority ordering/scores and blocker certainty against deterministic rules; the worker revalidates after persisted PR correlation.
- Added configurable WORKFLOW_TIMEOUT_SECONDS (120 default, maximum 300), safe timeout/provider/validation failure categories and completion/duration/audit records for interrupted claims.
- Added real LangGraph and worker regression tests in backend/tests/test_agents.py. Fixed explanations for legitimate zero-score tasks.
- Offline validation: eight scoring/blocker tests passed, all four result schemas accepted actual demo-adapter evidence, ranking normalization preserved deterministic output, and Python compilation passed. Updated LangGraph/PostgreSQL tests have not run in this authoring session, which cannot access Docker.

## Phase 3 direct validation attempt
- At the user's request, directly ran the dedicated database-test command and demo Compose rebuild. Both exited 1 because this session is denied access to /Users/arnavdesai/.docker/run/docker.sock.
- Directly ran scripts/verify_demo.py; it exited 1 with urlopen Operation not permitted because local HTTP access is restricted.
- No updated container test result, rebuilt deployment or successful acceptance report is claimed. Phase 3 runtime validation remains pending execution in an environment with Docker and localhost access.

## Phase 3 PostgreSQL validation passed
- User-run database-test profile rebuilt the updated backend and passed **77 tests in 6.41s**. Ruff: **All checks passed**. No Alembic deprecation warnings appeared in the supplied output.
- This validates the new real LangGraph routing/output-boundary tests and worker timeout/provider-failure/recovery tests against PostgreSQL, alongside existing coverage.
- User-run demo Compose rebuild succeeded; PostgreSQL/backend healthy, frontend running, migration exited and seed/worker started.
- Updated deployed end-to-end verification remains pending. The current verification-report.json still contains earlier events 10–14 and does not establish acceptance for this rebuild.

## Phase 3 complete
- User-run updated scripts/verify_demo.py passed all nine acceptance checks: service availability, authentication/RBAC, queue submission, webhook signature rejection/deduplication, workflow completion, persisted dashboard results and completion audits.
- Events **423–427** succeeded on their first attempt, covering PR analysis, sprint summarization, blocker detection and task prioritization.
- Directly inspected verification-report.json and confirmed the nine checks, demo mode and event IDs 423–427.
- Combined with **77 PostgreSQL tests in 6.41s**, clean Ruff and the rebuilt demo deployment, Phase 3 is complete.
- Next phase: audit and harden demo/live GitHub and Jira adapters and provider error handling. Live credentials and real-provider acceptance remain separate.
