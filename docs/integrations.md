# GitHub and Jira integrations

Demo Mode is the default. It uses local fixtures, requires no provider credentials and exercises the same workflow result schemas. Tests run live adapter code through httpx.MockTransport without making network requests. Provider adapters perform GET requests only; they do not approve, merge, comment or edit issues.

## Enable Live Mode

Provision a project with its real GitHub owner/repository, Jira project key and Jira board ID using the command in README. The seeded project points to a demo repository; configuring credentials alone does not change its provider identities.

Configure the private `.env` file:

| Variable | Value |
| --- | --- |
| MODE | live |
| GITHUB_TOKEN | Token with read access to the selected repository and pull requests |
| GITHUB_WEBHOOK_SECRET | Private signing secret matching the GitHub webhook |
| JIRA_URL | Jira Cloud site origin, such as https://your-team.atlassian.net |
| JIRA_EMAIL / JIRA_TOKEN | Account email and an API token compatible with site-based Basic authentication |
| JIRA_WEBHOOK_SECRET | Private secret for the supported Jira Automation ingestion rule |
| JIRA_ISSUE_API | enhanced (default); legacy explicitly selects the older offset endpoint |
| JIRA_SPRINT_ID | Optional positive ID selecting one active sprint on the configured board |
| JIRA_STATUS_MAP | JSON map from installation status names to scoring vocabulary |
| JIRA_SEVERITY_FIELD | Optional customfield_ID field name |
| JIRA_SEVERITY_MAP | JSON map from field labels to integers from 0 through 10 |
| LLM_PROVIDER | demo for initial real-data verification; openai-compatible only for approved real inference |
| LLM_INFERENCE_ENABLED | false; true only after explicit approval to activate real inference |
| LLM_API_KEY / LLM_BASE_URL / LLM_MODEL | Your prepared model provider settings; unnecessary for demo inference |

Do not copy credentials into Git or use scoped Jira tokens requiring the api.atlassian.com gateway with this site-based adapter. Gateway/OAuth authentication is not implemented. Jira site URLs reject user information, paths, queries, fragments, non-HTTPS protocols and hosts outside tenant.atlassian.net. Redirects are not followed.

For example, map custom statuses with `JIRA_STATUS_MAP={"Doing":"In Progress","Finished":"Done","Waiting":"Blocked"}`. Map an existing severity field with `JIRA_SEVERITY_FIELD=customfield_10001` and `JIRA_SEVERITY_MAP={"Critical":4,"Major":3,"Minor":1}`. Unmapped severity values contribute zero; configure mappings to match your actual installation. Completed status vocabulary is Done/Closed/Resolved, compared without case sensitivity.

Restart services to load environment changes:

```bash
docker compose up --build -d backend worker
```

Run a read-only adapter check using an existing project and PR number:

```bash
docker compose exec -T backend python -m app.integrations.check --project-id 1 --pr-number 42
```

Replace the IDs with actual resources when using Live Mode. The check retrieves PR and sprint data, prints counts and provider identities, makes no LLM requests, and performs no external writes. It also works against demo fixtures. Credentials are required only for real-provider checks; missing credentials do not prevent demo development.

## Retrieval and completeness

GitHub collection retrieves PR metadata, file pages and commit pages. Metadata counts must match retrieved counts. The PR commit endpoint supports at most 250 commits, so larger PRs fail explicitly. Changed files are limited to 3,000; larger PRs fail explicitly. Supporting larger commit histories would require a separate comparison strategy rather than claiming that the capped endpoint returned everything. PR number and URL must match the requested repository/resource.

Jira active-sprint enumeration advances by the actual number of rows returned. Boards with multiple active sprints require JIRA_SPRINT_ID, avoiding an arbitrary selection. The enhanced issue endpoint follows continuation tokens and rejects missing or repeated tokens. The legacy compatibility endpoint advances by the actual returned issue count, not the requested page size. Empty nonterminal pages and malformed metadata fail explicitly. Retrieval is bounded to 10,000 issues and 200 issue requests. A busy board or small server page size may hit the request limit before the issue limit; it fails rather than truncates. Issues outside the configured project are filtered; duplicate project issue keys fail validation. Only inward blocking links become dependencies, with duplicates removed. Results reflect issues visible to the configured Jira account, not necessarily all organizational issues.

## Failures and scheduling

Transport failures, HTTP 429, rate-limit HTTP 403 with Retry-After or an exhausted remaining quota, and HTTP 5xx are retryable. Ordinary permission/authentication/not-found errors and malformed/configuration failures are terminal. GitHub 403 secondary limits without rate-limit headers are treated as permission failures; inspect provider access outside the application if this occurs.

Retry-After seconds or HTTP dates and GitHub X-RateLimit-Reset are converted to safe delays. The worker persists the larger of exponential backoff and provider delay in available_at, so another queued event can execute while the limited event waits. Delay values are bounded to 24 hours and attempts remain bounded by MAX_ATTEMPTS. Invalid/nonfinite/negative delay values fall back to normal backoff. No provider response bodies or credentials enter stored errors. LLM request failures still use the ordinary bounded retry policy; provider-specific LLM rate-limit headers are not yet propagated.

## Validation

```bash
docker compose --profile database-test run --build --rm backend-tests
docker compose --profile demo up --build -d
python3 scripts/verify_demo.py
docker compose exec -T backend python -m app.integrations.check --project-id 1 --pr-number 42
```

Real-provider acceptance requires your own credentials and resources. Passing mocked HTTP tests or demo verification does not establish live connectivity.

## API references

- [GitHub pull request endpoints and collection limits](https://docs.github.com/en/rest/pulls/pulls)
- [GitHub rate limits and response headers](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [Jira sprint endpoints, including enhanced token pagination](https://developer.atlassian.com/cloud/jira/software/rest/api-group-sprint/)
- [Jira board sprint enumeration](https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/)

## Diagnose a failed connection independently

The check identifies whether a provider error occurred during GitHub PR retrieval or Jira sprint retrieval. Select a provider to avoid one provider's failure preventing diagnosis of the other:

```bash
docker compose exec -T backend python -m app.integrations.check --project-id 2 --provider jira
docker compose exec -T backend python -m app.integrations.check --project-id 2 --provider github --pr-number 1
```

Replace project/PR IDs with actual resources. A repository may exist without PR number 1. GitHub also uses 404 for inaccessible private resources; check token repository selection, permissions and organization approval. A Jira 404 can indicate an incorrect board ID, insufficient board visibility or unavailable endpoint. Rebuild the backend after changing check.py. These commands make no LLM calls.

Live data can now use the deterministic demo model independently. See docs/live-workflow-verification.md for safe real-data workflow and dashboard acceptance.
