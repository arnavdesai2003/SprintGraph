# SprintGraph


SprintGraph automates advisory engineering analysis using FastAPI, PostgreSQL, LangGraph and a Next.js dashboard. It includes PR analysis, sprint summaries, evidence-backed blocker detection and deterministic task prioritization. Demo mode works without GitHub, Jira or LLM credentials once dependencies are installed.

**Status:** Local demo MVP verified. Docker services, migrations/seeding, all four workflows, authentication/RBAC, signed/deduplicated ingestion, persisted results and audit records passed acceptance. Backend: **51 PostgreSQL tests passed**, Ruff passed. Frontend build/typecheck passed; ESLint had zero errors and two now-corrected configuration warnings. Browser acceptance: **4 Playwright tests passed**. Reports: `verification-report.json` and `artifacts/e2e/playwright-report/index.html`. Live integrations and historical productivity claims remain unverified. See PROGRESS.md.

## Start locally on macOS

Install Docker Desktop and start its daemon. From the repository root:

```sh
python3 scripts/setup_env.py
# If .env already exists, the script preserves it. This workspace already has a private generated .env.
lsof -iTCP:3000 -iTCP:8000 -sTCP:LISTEN
docker compose --profile demo up --build -d
docker compose logs -f migrate seed backend worker
```

PostgreSQL has no published host port, so an existing database on port 5432 can remain running. Migrations execute as a one-shot service before the backend starts; the demo profile runs an idempotent seed service. The worker processes seeded workflows. If ports 3000/8000 are occupied, stop the conflicting local process or adjust Compose ports and FRONTEND_ORIGIN/API URL together.

Open http://localhost:3000. Sign in as `admin@sprintgraph.local` or `developer@sprintgraph.local` using DEMO_PASSWORD from `.env`. Backend health is http://localhost:8000/health, readiness is http://localhost:8000/ready, and API docs are http://localhost:8000/docs.

Verify services, development authentication, RBAC, signed ingestion, duplicate protection, all four workflows, persisted dashboard results and audit records:

```sh
python3 scripts/verify_demo.py
```

This writes a local `verification-report.json` without credentials. It adds five demo events and waits up to two minutes for the worker.

Submit an authenticated GitHub fixture:

```sh
python3 scripts/submit_demo_event.py
```

The first submission queues a PR analysis; repeat submissions return duplicate=true. View it on Pull Requests. Sprint Insights and Task Priorities offer regeneration controls; Workflow Activity shows attempts and results. Settings and audit records require Admin. The seed already queues all four workflows.

## Validate

```sh
docker compose exec backend pytest -q
docker compose exec backend ruff check .
```

The frontend runtime image contains build output. Run its source checks in the build-stage image:

```sh
docker build --target build -t sprintgraph-frontend-check frontend
docker run --rm sprintgraph-frontend-check npm run typecheck
docker run --rm sprintgraph-frontend-check npm run lint
```

For reproducible verification of migrations and seeded workflows against PostgreSQL, CI runs Alembic, the seed command, and a 40-event demo evaluation in addition to API tests. Unit/API tests default to an isolated SQLite database. For Phase 2 PostgreSQL migration/concurrency acceptance, use the dedicated test database profile:

```sh
docker compose --profile database-test run --build --rm backend-tests
```

This runs pytest and Ruff against a separate sprintgraph_test database with a disposable schema; it does not reset the demo database. The PostgreSQL race test is explicitly skipped in the SQLite-only run. Run real-service browser acceptance after rebuilding the frontend for the accessible Sign out label:

```sh
docker compose --profile demo up --build -d frontend
docker compose --profile demo --profile test run --build --rm e2e
```

Four Playwright tests cover dashboard navigation, evidence, PR regeneration, role restrictions, confirmation cancellation and sign-out. Reports/screenshots are in `artifacts/e2e`. See docs/demo-validation.md for details.

## Develop without Docker

Requires Python 3.12+ and Node 22+ with internet access for dependency installation.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e './backend[dev]'
# Run these from backend with root .env variables exported, or copy the private .env into backend temporarily.
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.seed
../.venv/bin/uvicorn app.main:app --reload --port 8000
# In another terminal, same directory and environment:
../.venv/bin/python -m app.worker
# In another terminal:
cd frontend
npm install
npm run dev
```

A safer environment-loading helper avoids copying secrets:

```sh
# From root, launches commands with root .env loaded:
.venv/bin/python scripts/backend_command.py alembic upgrade head
.venv/bin/python scripts/backend_command.py python -m app.seed
.venv/bin/python scripts/backend_command.py uvicorn app.main:app --port 8000
.venv/bin/python scripts/backend_command.py python -m app.worker
```

The `.env.example` defaults to SQLite for host development. Docker overrides DATABASE_URL to its internal PostgreSQL service. Generated passwords are hexadecimal so they are safe in the connection URL. Do not commit `.env`. Stop containers with `docker compose down`; omit `-v` to retain your database.

## Live integrations

Provision a fresh organization, administrator and project through the local operator command (password is entered privately):

```sh
docker compose exec backend python -m app.provision --organization "Engineering" --email "you@example.com" --repository "your-owner/your-repo" --jira-key "TEAM" --board-id 12
```

Use your actual repository, Jira project key and board ID. This command preserves existing organizations and rejects duplicate emails/repositories. A project setup UI is not yet included. Set MODE=live, GITHUB_TOKEN (read access to the configured repository), GITHUB_WEBHOOK_SECRET, JIRA_URL (HTTPS Jira Cloud site), JIRA_EMAIL, JIRA_TOKEN, JIRA_WEBHOOK_SECRET, LLM_PROVIDER=openai-compatible, LLM_API_KEY, LLM_BASE_URL and LLM_MODEL. Restart backend/worker after environment changes. Demo seeding is disabled in live mode. Existing local demo users are not a production identity system.

Configure GitHub pull_request webhooks at `/api/webhooks/github`, with the same signing secret. For Jira, configure an Automation rule to POST issue identity JSON to `/api/webhooks/jira/{project_id}`, with `Authorization: Bearer <JIRA_WEBHOOK_SECRET>` and a stable unique `X-Delivery-ID` for that occurrence. Jira native unverified webhooks are unsupported. Local loopback endpoints are not internet accessible; no public deployment or tunnel is configured.

All integrations are read-only. The platform never approves/merges PRs or modifies Jira issues. Failures and rate limiting enter bounded retries. See docs/architecture.md for provider pagination, authentication and worker limits.

## Evaluation

```sh
python3 scripts/run_evaluation.py --events 400
```

The wrapper pauses the ordinary worker if it is running and restarts it in a finally block. The evaluator itself processes only its own batch, preserving unrelated pending events. Evaluation writes synthetic events and results to the demo database; use a disposable Compose project/database for isolated benchmarking. Reports define successful/failed events, attempts, automated/manual handling, P50/P95 end-to-end latency using nearest-rank percentiles, per-workflow counts, wall time and throughput. Reports record source hashes, runtime and non-secret scoring configuration. Evaluation requires the demo LLM provider and cannot make live or paid model calls. They do not substantiate the historical “41% automation across 537+ engineering events” claim. The measured 400-event local run is documented in [docs/evaluation.md](docs/evaluation.md); new reports always come from execution, not hardcoded results.

## Repository

- `backend/app/`: API, security, integrations, workflows, persistence and services
- `backend/alembic/`: versioned schema migration
- `backend/tests/`: workflow, provider, security, ingestion and scoring tests
- `frontend/`: six dashboard pages and reusable components
- `scripts/`: private environment setup, signed demo submission and offline checks
- `docs/`: design decisions and acceptance checklist
- `.github/workflows/ci.yml`: backend/frontend validation

Captured dependency locks are present for frontend, browser tests and the Linux backend. Locked frontend/backend rebuilds and 42 backend tests passed. Keep lockfiles under version control; regenerate intentionally after dependency changes.


## Capture resolved dependencies

The existing frontend build-stage image contains the lockfile generated during the successful installation. Export it without resolving dependencies again:

```sh
docker run --rm sprintgraph-frontend-check cat /app/package-lock.json > frontend/package-lock.json
```

Future frontend builds use npm ci when the lock exists. After the browser image builds, export its lock similarly using `docker compose --profile demo --profile test run --no-deps --rm --entrypoint cat e2e /tests/package-lock.json > e2e/package-lock.json`.

For a complete snapshot of the validated backend environment:

```sh
docker compose exec -T backend python -m pip freeze --exclude sprintgraph > backend/requirements.lock
```

The backend freeze is generated in the Linux container, matching its deployment platform. Keep pyproject.toml as the direct dependency definition and review/regenerate the lock after dependency changes. No lock contents or benchmark results have been fabricated.


For validated dependency capture and locked rebuilds, prefer:

```sh
python3 scripts/capture_locks.py
docker compose --profile demo up --build -d
docker compose exec -T backend pytest -q
docker compose exec -T backend ruff check .
```

This captures existing resolved frontend/browser packages and backend versions without re-resolution. Backend Docker/CI install the frozen requirements followed by the local package with --no-deps and pip check; frontend/browser builds use npm ci. Do not reuse the Linux backend snapshot directly on macOS. The locks pin package versions but do not pin container base image digests or provide Python wheel hashes.
