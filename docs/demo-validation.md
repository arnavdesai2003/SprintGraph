# Local acceptance checklist

These are commands and expected assertions, not claimed results from the authoring session.

1. `docker compose --profile demo up --build -d` builds both applications; db/backend/frontend health checks pass and migrate/seed exit 0.
2. Open localhost:8000/docs, test /health and /ready. Anonymous /api/projects returns 401.
3. Sign in to localhost:3000 with the generated demo password. Overview shows database events and marks measurements demo.
4. Run `python3 scripts/submit_demo_event.py`. It returns event_id. Repeat it and check duplicate=true.
5. Pull Requests displays PR #43, linked issue keys, advisory risks/testing suggestions and source evidence.
6. Regenerate sprint summary, blockers and priorities. Workflow Activity transitions pending → running → succeeded, with persisted structured output and durations.
7. Sprint evidence shows source issue data. Potential stalled tasks differ from definite blocked/overdue evidence.
8. Developer sign-in can run analysis but cannot access Settings or audit. Admin role changes require explicit confirmation and create an audit record.
9. Run pytest, Ruff, frontend lint/typecheck/build. Run migrations and seed again and verify no duplicate seed events.
10. Restart the worker; pending events remain durable. Fault-inject provider failure in tests to verify bounded retries.

Do not expose this local authentication stack publicly. Record actual command results and screenshots only after these checks run.

## Automated browser acceptance

Four Playwright tests cover navigation through all six pages, saved evidence, definite versus potential blocker labels, PR regeneration through queued execution into a rendered result, Developer RBAC, canceled permission confirmation, sign-out, and uncaught browser errors.

```sh
docker compose --profile demo up --build -d frontend
docker compose --profile demo --profile test run --build --rm e2e
```

The test container shares the frontend network namespace and forwards localhost:8000 to the backend. Chromium visits localhost:3000 and uses the actual configured CORS origin. No mocked API responses or CORS bypasses are used. Only DEMO_PASSWORD is passed into the test container. Tests add one advisory PR event; the permission dialog is canceled. Browser traces/videos are disabled to avoid capturing login request credentials. HTML reports and screenshots are saved in artifacts/e2e and ignored by Git.

User-run browser acceptance completed: **4 passed in 6.6s**. The generated local report records status passed and no failed tests. Browser acceptance is closed for the demo MVP.
