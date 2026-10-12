# SprintGraph progress

## Current status
The local demo MVP acceptance checks are complete: healthy Docker services, migrations and seeding, development authentication/RBAC, verified ingestion, all four LangGraph workflows, persisted dashboard results, audit records, 99 PostgreSQL backend tests plus 12 subtests, frontend build/typecheck, and four real-service browser tests passed. ESLint passed with zero errors; its two configuration warnings were corrected in source. Dependency snapshots were captured and validated through locked rebuilds. A 400-event synthetic demo evaluation completed successfully; observed measurements are documented in docs/evaluation.md.

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
Local authentication requires organizational OIDC/session hardening before production. Single-worker recovery lacks heartbeat/fencing and node checkpointing. LLM retry windows do not honor rate-limit headers. Live Jira mappings require installation-specific configuration; GitHub/Jira header scheduling and mapping support passed Phase 4 local acceptance. No project provisioning UI exists yet. Browser E2E coverage passed locally; CI execution is not yet verified. Historical 41% automation across 537+ events remains unverified.

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

## Phase 4 implementation increment (container acceptance pending)
- Audited official GitHub/Jira API references. GitHub now validates metadata counts and rejects incomplete data or PRs above the 250-commit/3,000-file endpoint limits.
- Added enhanced Jira continuation-token pagination and an explicit legacy offset compatibility mode. Offsets advance by actual page size; missing/repeated tokens, stalled pages and duplicate issue keys fail visibly.
- Added explicit selection for parallel active sprints, configurable Jira status/severity maps, tenant URL validation and redirect rejection.
- Provider failures now carry safe retry eligibility and bounded Retry-After/reset delays. Worker persists delays without blocking other queue entries; permanent provider errors finish immediately.
- Added a read-only integration smoke-check CLI and docs/integrations.md with live setup, limits and compatibility requirements. Demo Mode remains credential-free.
- **19 live-adapter mocked HTTP unit tests passed offline**, as did the existing demo integration check script and Python compilation. Three new persisted-worker integration tests and the full PostgreSQL suite remain pending Docker validation. Live credentials were not used and real-provider connectivity is not claimed.

### Phase 4 validation attempt
- Repeated the 19 mocked HTTP adapter tests and eight scoring tests: all passed. Existing demo/provider integration check script passed; Python compilation and git diff --check passed.
- Directly attempted the full database-test Docker command; it exited 1 because this session is denied access to the Docker socket. The three new persisted-worker tests, full Ruff suite and rebuilt-stack acceptance are therefore not yet claimed.

## Phase 4 local MVP acceptance complete
- User-run dedicated PostgreSQL suite: **99 passed, 12 subtests passed in 7.97s**. Ruff: **All checks passed**.
- Updated demo Compose rebuild/startup succeeded, with healthy database/backend, frontend running and migration exited successfully.
- Updated deployed verifier passed all nine checks; events **428–432** succeeded on their first attempt with persisted results and completion audits. Directly inspected verification-report.json to confirm the checks, demo mode and event IDs.
- Read-only adapter CLI succeeded in Demo Mode for project 1: PR 42, two files, one commit; sprint demo-sprint-12, four issues; read_only=true and llm_calls=0.
- Phase 4 is complete for the local MVP. GitHub/Jira live HTTP paths are covered by mocked responses; real-provider connectivity is not claimed.
- Next: Phase 5 audit of authentication, RBAC, audit logs and dashboard interactions.

## Live connection diagnosis increment
- User switched to Live Mode and recreated backend/worker successfully. The combined live adapter check returned HTTP 404; its failing provider was not identified, so live connectivity remains unverified.
- Added --provider github/jira/all selection to the read-only check and provider-stage error labels, retaining retry eligibility/delay metadata. Jira checks do not require a PR number or successful GitHub connection.
- Six offline check-CLI unit tests passed; Python compilation and git diff --check passed. Full updated container tests and the live diagnosis commands remain pending.

## Live data / demo inference verification increment (runtime acceptance pending)
- Operator reports successful live GitHub/Jira reads for project 2, arnavdesai2003/SprintGraph PR 2, SPRIN board 2 and sprint 3. This is retrieval evidence, not yet workflow/browser acceptance.
- Inspected actual API triggers, graph, worker, persistence and dashboard queries. Removed the coupling that rejected live data with demo inference; added default-disabled LLM_INFERENCE_ENABLED gating for real model requests. Updated only LLM_PROVIDER=demo and LLM_INFERENCE_ENABLED=false in private .env, preserving other settings.
- Added observed node durations/statuses to persisted attempt audits, including failure paths and data/model configuration. Activity API and dashboard expose paths and show inference mode separately.
- Added a trusted local verifier for real HTTP triggers, PostgreSQL results, node audits, webhook deduplication and available RBAC boundaries, plus a read-only real-service browser verifier without seeding.
- Added automated live-adapter-to-graph/API/database tests with mocked HTTP, failure traces, deduplication/RBAC and forbidden paid inference. Compatible model preparation is tested with mocked responses only.
- Offline: three trace tests and nineteen adapter HTTP tests passed; Python compilation, modified TypeScript syntax/transpilation and Compose profile configuration parse passed. Full type checking, updated PostgreSQL tests/Ruff and browser execution are not claimed.
- Direct attempts to run Docker tests, rebuild services, execute the real verifier and obtain the browser session were blocked by Docker socket permissions. No real workflow event, result, browser pass or paid model request is claimed from this session.

## Real-data workflow and browser acceptance passed (2026-10-12)
- User-run app.verify_live for project 2, PR 2 and sprint 3 passed all checks. Events **433–435** progressed pending/running to succeeded: manual PR analysis, manual sprint summary and one signed PR delivery (the repeated delivery was deduplicated).
- Verified actual classify → collect → pull_request/sprint_summary → validate observations, PostgreSQL event/attempt/result records, completion audits and dashboard API results. Anonymous access, Developer Admin restrictions and available organization boundaries passed.
- Running API/worker used live integrations with demo inference; paid inference disabled. No external provider mutations or database reset occurred.
- User-run real-service Chromium acceptance: **1 passed in 675ms** (test body 384ms), verifying persisted PR/sprint display and observed node traces. Directly inspected artifacts/live-e2e/test-results/.last-run.json: passed, no failed tests. Browser runner locked npm-ci rebuild succeeded.
- No failures were reported in these two acceptance runs. Failure-path regression tests are implemented, but the updated full PostgreSQL pytest/Ruff result has not yet been supplied; the last confirmed full suite remains 99 tests plus 12 subtests from Phase 4.
- OpenAI-compatible inference remains prepared and disabled. No paid inference or real-model quality/cost acceptance is claimed.

## Gemini preparation — 2026-10-12
- Extracted compatible inference into agents/inference.py; configured only four nonsecret local LLM flags for Gemini 3.1 Flash-Lite, preserving the API key and integration settings. Inference remains disabled.
- Added zero-network `python -m app.agents.check`; local validation passed (key present, disabled, no fallback). Key validity and billing remain unverified.
- Eight mocked Gemini unittest cases passed: request contract, validated JSON, disabled guard, configuration safety, auth/parameter failures, 429/503 delay, timeout, malformed/extra output. Full Docker PostgreSQL/Ruff checks attempted but blocked by Docker socket permission.
- No live model call, database reset, provider mutation or service recreation performed. Activation awaits user approval after full checks. See docs/gemini.md.

### Gemini test assertion repair — 2026-10-12
User container run: 122 passed, 24 subtests passed, one outdated connection-error assertion failed. Updated test_failed_ai_request to assert the specific safe connection message, retryability and exclusion of private diagnostics/API key. Eight offline Gemini tests passed again. Full container rerun attempted but Docker socket access remains denied in this session; final PostgreSQL suite/Ruff outcome pending. Inference remains disabled.

### Single Gemini acceptance tooling — 2026-10-12
User reports Docker tests run and explicitly enabled inference. Added app.verify_gemini: authenticated PR-only event, worker event-ID isolation, process-local one-attempt limit, exact Gemini endpoint/model guard, one counted request and exclusive local report to refuse accidental repeats. Checks graph trace, PostgreSQL result/status, audit and dashboard API. Browser runner accepts --gemini-result-id to retrieve the exact saved analysis without submitting workflows. Added targeted-worker isolation regression test. Python compilation, eight offline Gemini tests and diff checks passed; Docker socket remains denied, so new container regression and real acceptance/browser execution remain pending. No real model request made by this session.

### Gemini verifier diagnostics repair — 2026-10-12
User one-shot command stopped without identifying its preflight cause. Added --diagnose (read-only config flags, key presence, report metadata, running event IDs; no inference/submission) and specific safe configuration/existing-report failure messages. Preserve one-shot marker and never automatically resubmit. Added mocked diagnostics/privacy and CLI error regression tests; compilation and diff checks passed, container execution pending due to session Docker access restriction. Actual request count and real acceptance remain unknown until the container report is inspected.

### Gemini real-data acceptance complete — 2026-10-12
User-run one-shot report passed for Project 2 / GitHub PR 2 using gemini-3.1-flash-lite: exactly one counted inference request, event 436 succeeded, execution 436, persisted PR result 117. Observed classify → collect → pull_request → validate nodes all succeeded; verifier confirmed PostgreSQL result, workflow audit and dashboard API retrieval. After starting the stopped frontend, read-only Chromium acceptance with --gemini-result-id 117 passed (1 test, 739 ms; test body 367 ms), confirming persisted analysis display and observed trace. No additional workflow was submitted by browser verification. Ordinary worker should remain stopped until further inference is authorized. User reports Docker tests completed; exact final suite counts not supplied. Google billing/free-tier status was not independently verified.

## Phase 5 security and dashboard hardening — 2026-10-12
- Authentication now requires exp/sub claims, validates a positive numeric subject and current known database role, and returns safe 401 responses for malformed claims. Existing tokens observe role revocation immediately.
- Successful login now emits an organization-scoped auth.login audit with actor ID and empty details; credentials/tokens are never stored in audits.
- Dashboard API helper handles non-JSON server errors with an informative safe status message instead of exposing parser errors.
- Added regression tests for six invalid token cases, login audit privacy, role revocation, deleted accounts, and all project/role organization boundaries. Python compilation passed; Docker PostgreSQL tests attempted but blocked by socket permissions. New suite and browser acceptance remain pending. No provider calls, inference, configuration changes or database reset occurred.

## Phase 5 runtime acceptance complete — 2026-10-12
Full session access enabled. Agent directly ran the isolated PostgreSQL Compose suite: 136 tests and 24 subtests passed in 12.95s; Ruff passed. Frontend production image build, TypeScript typecheck and ESLint passed without diagnostics. Rebuilt only backend/frontend with --no-deps; both healthy, ordinary live worker remained stopped. Read-only live browser check targeting Gemini result 117 passed (1 test, 644 ms). No new inference/provider workflow was submitted. Existing database, credentials and integration configuration preserved. This completes the Phase 5 local security/dashboard increment; organizational production identity requirements remain separate.

## Phase 6 local hardening acceptance — 2026-10-12
- Unified dashboard/evaluation nearest-rank percentiles and exposed workflow, latency sample, attempt and manual/automated metrics through the authorized overview API; regression verifies failure/manual accounting.
- CI now explicitly uses a dedicated PostgreSQL test database for pytest, demo inference and disabled real inference. GitHub-hosted execution remains unverified.
- Added infra/compose.demo-test.yaml for a separate demo Compose project on ports 3100/8100, preserving live services/database and disabling real inference.
- Direct Docker suite: 137 tests and 24 subtests passed in 11.90s; Ruff clean. Dedicated demo Chromium suite: all four tests passed in 6.5s. Phase 5 frontend build/typecheck/ESLint remain valid (no frontend changes in this increment).
- Controlled evaluation with separate demo worker stopped: 400 events succeeded, zero failed/unfinished, P50 1363.055 ms, P95 2444.229 ms, wall 2.764805 s, throughput 144.675671 events/s. Report artifacts/phase6-evaluation.json. An earlier trial overlapped the demo worker and is excluded from reported controlled metrics. These are synthetic mock-provider results, not production/historical productivity evidence.
- Live worker remained stopped; no real provider/inference calls made. Separate test stack shut down without deleting volumes.
