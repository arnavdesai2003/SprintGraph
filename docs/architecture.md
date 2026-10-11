# Architecture and decisions

SprintGraph is a modular monorepo. FastAPI accepts authenticated user requests and verified integration events. PostgreSQL stores events before HTTP acknowledgment. A separate Python worker claims pending rows and executes an actual typed LangGraph StateGraph:

```
START → classify/validate → collect allowlisted provider data
      → deterministic conditional route
      → PR analysis | sprint summary | blocker detection | priority ranking
      → structured validation → END
      → result + execution status + audit record committed together
```

## Reliability
The queue is a PostgreSQL table rather than an in-memory BackgroundTask. Ingestion enforces uniqueness on (source, delivery_id), including concurrent insert conflicts. The worker uses SELECT FOR UPDATE SKIP LOCKED and commits a claim before provider requests. Failures retry up to MAX_ATTEMPTS with bounded exponential delay (2, 4, … seconds, capped at 300). Every attempt has a workflow execution record. A crashed running claim is recovered after ten minutes. External calls have bounded timeouts. The first release supports one worker; the stale claim policy has no heartbeat or fencing token, so do not scale concurrent workers or allow workflows longer than the lease. Recovery occurs continuously and on startup. SQLite is an optional test/local fallback and does not provide PostgreSQL row-lock semantics.

The MVP persists events, attempts and results, but does not checkpoint individual LangGraph nodes. A recovered workflow repeats read-only collection and analysis. Replace the polling loop with a worker using leases, heartbeat, fencing and LangGraph Postgres checkpoints if longer workflows or multiple workers are needed. No Redis, Kafka or Kubernetes is required.

## Data
Eleven tables represent organizations, users, projects, integration configurations, events, executions, four result types, and audit logs. Project-scoped indexes support results lookup. Providers are correlated using repository/PR identity, Jira issue keys, and sprint IDs. Source evidence is stored alongside each result for inspection. A frozen initial Alembic migration ensures later model edits cannot rewrite history. Provider secrets are environment variables, never database JSON configuration.

## Permissions and model boundaries
Argon2 password hashes, expiring HS256 JWTs, strict algorithm selection and database-resolved roles protect API endpoints. Every project query checks organization membership. Admin-only settings, audit access and role changes are enforced server-side. Role changes require confirmed=true and cannot change the caller's own role. UI restrictions are supplementary.

Provider adapters expose only read operations. AI summaries are advisory. The LLM never receives command execution, SQL or mutation tools; deterministic code controls routes and ranking. PRIORITY_WEIGHTS accepts a JSON map through the environment; due-date, severity, dependency and status contributions are explicit in services/scoring.py. Pydantic validates model outputs. PR descriptions and issues are untrusted evidence, not instructions. No approval/merge/comment/Jira-update tools are enabled. Future external writes must introduce explicit approval records scoped to action, resource, approver, payload hash and expiry, then recheck RBAC and idempotency before execution.

## Authentication scope
Seeded demo accounts use a locally generated private password, not hardcoded public credentials. Browser JWTs are held in sessionStorage and expire after eight hours. This is a local demonstration authentication implementation. Before production deployment, adopt organizational OIDC, Secure/HttpOnly session cookies, CSRF protection where applicable, rate limiting at the ingress, HTTPS, signing-key rotation, session revocation and account lifecycle management. The project binds published Docker ports to loopback. Do not expose the local stack publicly.

## Integrations
Demo adapters require no paid services. GitHub live requests collect metadata, all supported changed-file pages, and commit pages. Jira uses the configured board's first active sprint and paginated issues filtered to the configured project key. The conservative pagination limits fail visibly rather than silently truncate. Live blocker correlation uses saved PR analyses; unknown dependencies outside the retrieved sprint are labeled potential. Severity defaults to zero in live Jira because field IDs differ by installation. Status vocabulary and issue link meanings need adaptation for custom Jira workflows.

GitHub ingestion verifies raw-body HMAC SHA-256 and uses delivery headers for deduplication. Jira ingestion supports an Automation for Jira rule that sends a configured shared-secret Authorization header and stable X-Delivery-ID. It does not accept unverified native webhooks. Payloads trigger authoritative retrieval rather than directly determining live analysis evidence.

Provider 429/5xx/transport errors become safe failures and are retried by the queue. Retry-After and GitHub reset windows are not yet honored; the bounded retry policy may exhaust before a provider limit resets. Error categories and execution IDs are logged without provider bodies or secrets.

## Measurement
Overview latency measures ingestion to completion including queue wait and retries. Execution duration records each attempt. Synthetic evaluation reports are explicitly labeled and never establish historical productivity savings. Read-only workflow completion is the MVP definition of automated handling; manual triggers still automate analysis. There is no implemented manual-handling UI or production counterfactual measurement.

## Frontend
Six Next.js App Router pages consume backend APIs. TanStack Query refreshes pending work. Recharts renders actual sprint distributions. Tailwind and local shadcn-style Radix components provide responsive UI. Settings exposes configuration presence, not secrets. Dependency installation and browser validation must pass before declaring the dashboard verified.


## Browser acceptance runner
An optional Compose test profile runs Playwright Chromium outside the production runtime images. It shares the frontend network namespace and forwards the local API port to the backend service, preserving real browser-origin/CORS behavior. Tests exercise real seeded services and database results. Artifacts stay local and traces are disabled. This service is a test runner, not an additional production microservice.


## Evaluation and dependency snapshots
Evaluation claims only events whose delivery IDs belong to its run, so unrelated pending work is preserved. The runner pauses/restarts the ordinary worker and writes the measured report locally. Metrics use nearest-rank percentiles and count only successful automated events in the successful automation numerator. Empty datasets have no automation percentage. Demo-only provider enforcement prevents accidental live model calls. Reports include code hashes, configuration and runtime metadata. No manual baseline or historical productivity saving is simulated.

Dependency snapshots are captured from previously tested Docker environments. npm locks retain integrity values; Python freeze pins Linux package versions and rejects direct/editable URLs. Locked backend installs use --no-deps for the application and pip check. Frontend, browser and backend snapshots were captured locally. Locked frontend/backend rebuilds passed; browser npm-ci rebuild remains a separate check. Container image digest pinning, Python artifact hashes and cross-platform lock resolution remain further reproducibility work.


## Phase 2 ingestion collision and database acceptance
A delivery ID identifies a source event across the deployment. A repeated delivery returns the original event only when project, workflow type and normalized payload match. Conflicting reuse returns a generic HTTP 409 without another project's event ID. The same consistency check runs after a database unique-constraint race; unrelated constraint errors are not mislabeled duplicates.

The optional database-test Compose profile runs the full suite against a separate PostgreSQL database named sprintgraph_test. Its fixture creates a randomly named schema, scopes connections to that schema and removes it at exit. A name guard refuses production/demo databases. A synchronized two-connection test forces both delivery lookups to observe absence before competing inserts, then checks exactly one event and audit record. A frozen migration roundtrip tests schema consistency and seeding. These new acceptance checks are not considered passed until the container suite executes.

## Phase 3 structured workflow boundaries
The graph uses explicit typed state with a validated project snapshot, validated event parameters and a UTC reference date captured during classification. Only PR retrieval or sprint retrieval is selected by the validated event type. Provider evidence passes strict Pydantic schemas before analysis; PR repository/number/URL must match the request and sprint issue keys must belong to the configured Jira project. Duplicate issue keys fail rather than distort metrics.

Full output schemas reject unexpected execution fields and preserve normalized source evidence. Final validation recomputes sprint counts/progress, deterministic priority scores/order and blocker findings/certainty. Model prose cannot override those rules. Saved PR evidence supplies blocker links during persistence, followed by another output validation. A valid zero-score task receives a nonempty explanation.

WORKFLOW_TIMEOUT_SECONDS bounds the entire graph execution (default 120 seconds, accepted range 1–300), below the ten-minute interrupted-claim threshold. Timeout, provider and validation errors persist safe categories and use the existing bounded retry policy. Terminal interrupted claims receive completion timestamps, attempt durations and recovery audits. This remains a single-worker design without individual node checkpoints or fencing.

Phase 3 local acceptance passed: 77 PostgreSQL tests, clean Ruff and rebuilt-stack end-to-end verification for events 423–427. All four workflows produced persisted results and audits on their first attempt. This validates demo execution; it does not establish live-provider acceptance.
