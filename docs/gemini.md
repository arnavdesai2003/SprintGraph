# Gemini inference

SprintGraph uses the existing OpenAI-compatible Chat Completions adapter with Google's endpoint. No SDK or additional dependencies are needed. Existing LangGraph routing, source integrations, result validation and persistence remain in place.

Private `.env` configuration:

```dotenv
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-3.1-flash-lite
LLM_API_KEY=<your private Gemini key>
LLM_INFERENCE_ENABLED=false
```

The key is never printed. Local configuration validation makes zero network requests and cannot verify credentials, quota, model availability or billing tier. Google lists this model's standard free tier; ensure the key's Google project remains on the free tier. SprintGraph cannot enforce a Google billing tier from a key.

Validate the updated container implementation while disabled:

```sh
docker compose --profile database-test run --build --rm backend-tests
docker compose up --build -d backend worker
docker compose exec -T backend python -m app.agents.check
```

Gemini requests omit forced temperature, use JSON response mode, and pass results through strict Pydantic Analysis validation. The graph subsequently validates complete results and deterministic business rules before persistence. Invalid responses never become successful results. Authentication/permission errors and invalid parameters are terminal; 429 honors bounded Retry-After; timeouts and 5xx use existing bounded worker retries. There is no provider/model fallback or automatic billing change. Provider bodies, keys and request headers are excluded from errors.

After tests pass and explicit user approval, enable `LLM_INFERENCE_ENABLED=true` and recreate backend/worker. Enabling affects every queued workflow; inspect/drain the queue while inference remains disabled before activation. For the requested exactly-one-call acceptance run, disable retries for that run or isolate it in a controlled worker execution: ordinary worker retries may otherwise issue additional requests after a timeout or 429. Submit only Project 2 PR 2 once, verify classify → collect → pull_request → validate, result persistence, audits, and browser display. Do not use `app.verify_live` because it intentionally requires demo inference. No real inference has been authorized or performed in this increment.

References: https://ai.google.dev/gemini-api/docs/openai and https://ai.google.dev/gemini-api/docs/pricing

## Approved one-shot acceptance

With the user-approved enable flag already set, keep the ordinary worker stopped throughout verification:

```sh
docker compose stop worker
docker compose --profile database-test run --build --rm backend-tests
docker compose up --build -d backend
docker compose exec -T backend python -m app.agents.check
docker compose exec -T backend python -m app.verify_gemini --project-id 2 --pr-number 2
docker compose exec -T backend cat /tmp/sprintgraph-gemini-once.json
```

Only this new event is processed; other pending events are left alone. The local verifier disables retries in its own process and permits at most one model POST. On failure do not delete the report or automatically rerun; a timeout may still have consumed the original request. Stopping worker assumes this Compose deployment's single worker and no other manual processors.

If the report passes, use its `result_id`:

```sh
python3 scripts/verify_live_browser.py --project-id 2 --pr-number 2 --sprint-id 3 --gemini-result-id RESULT_ID
```

This is a read-only browser check. Gemini selection uses `--no-deps` to avoid starting the stopped ordinary worker. Backend and frontend must already be healthy. Keep the worker stopped after acceptance; restoring ordinary processing with inference enabled would authorize additional calls. No other workflow is submitted by this verifier or browser check.

## Recorded acceptance — 2026-10-12

User-provided container report confirmed Project 2, GitHub PR 2, model gemini-3.1-flash-lite, exactly one inference request, succeeded event/execution 436 and persisted result 117. Observed classify, collect, pull_request and validate nodes all succeeded. The verifier checked persistence, audit and dashboard API retrieval. User-run Chromium verification targeting result 117 passed: one test in 739 ms. The browser retrieved the saved analysis without submitting another workflow. This establishes the requested one-shot real-model acceptance; it does not independently verify the Google project's billing tier or authorize ongoing inference.
