# Live data with deterministic demo inference

Integration retrieval and model inference are independent. Keep MODE=live for real GitHub/Jira GET requests and LLM_PROVIDER=demo for deterministic local analysis. LLM_INFERENCE_ENABLED=false prevents real model calls even if an API key exists. No GitHub or Jira mutation tools are provided.

Verified provider configuration supplied by the operator: project 2, repository arnavdesai2003/SprintGraph, PR 2, Jira key SPRIN, board 2 and sprint 3. Real workflow acceptance passed on 2026-10-12 for events 433–435, and the real-service browser test passed in 675ms. The updated full backend regression suite remains pending its separate execution result. Existing credentials, project identities, URL/model settings and database contents are preserved. Only the requested inference selection and disabled enablement flag were updated in the private environment.

## Trigger mechanisms

Authenticated Admin and Developer users in a project's organization can POST /api/projects/{project_id}/run with {"workflow":"pull_request","number":2} or {"workflow":"sprint_summary"}. GitHub signed webhooks also enqueue PR workflows; supported Jira Automation webhooks enqueue blocker workflows. Manual requests represent new runs; verified webhook delivery IDs provide deduplication.

The API commits a pending event before returning HTTP 202. A separate worker commits a running attempt, executes the actual StateGraph, validates the structured result and commits status/result/audit together:

```text
classify → collect → pull_request → validate
classify → collect → sprint_summary → validate
```

The collect node calls the real read-only adapters in Live Mode. Demo describe returns validated deterministic prose without constructing an LLM request. Node wrappers observe actual started/completed/failed nodes and durations. The worker persists these observations in the existing audit JSON, including data mode, model provider and inference-enabled flag; no schema reset or new migration is needed. Activity exposes the trace to organization-authorized users. A failed node retains a partial trace with no provider exception body. Existing bounded attempts/backoff and provider delays still apply.

## Run acceptance safely

Run these commands from the repository root, in order:

```bash
# Isolated test database/schema; does not reset the application database.
docker compose --profile database-test run --build --rm backend-tests

# Load the new code and disabled-inference settings into API and worker together.
# Do not use the demo profile or run seed against Live Mode.
docker compose up --build -d --force-recreate backend worker frontend

docker compose exec -T backend python -m app.verify_live --project-id 2 --pr-number 2 --sprint-id 3

python3 scripts/verify_live_browser.py --project-id 2 --pr-number 2 --sprint-id 3
```

The backend verifier adds two manual workflow events and one locally submitted signed PR event to the existing application database. It repeats that signed delivery to confirm deduplication, and rejects an invalid signature. It never sends a mutation to either provider, changes users/roles, seeds data or resets the database. It refuses to enqueue if the running API is not in Live Mode with demo inference and real inference disabled.

The verifier issues a five-minute organization-admin session using trusted local database access, without asking for or printing an account password. It calls the real HTTP API and relies on the running worker. Anonymous submissions must fail; an existing Developer account must fail Admin APIs, and an available cross-organization account must fail project access. Missing Developer accounts are reported as a skipped live check rather than manufactured evidence; automated tests cover those boundaries.

After completion it independently checks PostgreSQL event/attempt/result/audit rows and the dashboard API representations, including the exact PR/sprint identities and actual node observations. Failures remain stored; a timeout does not delete queued events. The report stores counts/IDs/statuses/traces, never credentials or source payloads. Save the report locally if desired:

```bash
docker compose cp backend:/tmp/sprintgraph-live-workflow-report.json ./live-workflow-report.json
```

The browser runner captures a short-lived session in memory, passes it through the process environment and never puts it in command arguments or logs. Its optional live-test Compose runner has no seed dependency. Chromium retrieves persisted PR/sprint results from the actual API and asserts that their titles/summaries and successful node path appear in the Next.js dashboard. It submits no workflows or role changes. Traces and video remain disabled; local failure screenshots/reports are ignored by Git under artifacts/live-e2e.

## Prepare future compatible model inference

The compatible Chat Completions adapter and Pydantic output validation remain implemented. A mocked-response integration test exercises that path without a real model request; another verifies that API keys alone cannot enable inference.

Retain your configured LLM_BASE_URL, LLM_MODEL and private LLM_API_KEY. The current adapter uses JSON-object mode followed by application schema validation. JSON mode guarantees JSON syntax rather than schema adherence, so the validation node remains necessary. See [official OpenAI structured-output documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat). Provider/model support for JSON mode must be checked before enabling that provider.

Only after explicit approval should an operator select LLM_PROVIDER=openai-compatible and LLM_INFERENCE_ENABLED=true, then recreate backend and worker. Real inference is not activated by this verification. A separate approved run must measure actual model outputs, errors, usage and cost; demo success does not establish real inference acceptance.
