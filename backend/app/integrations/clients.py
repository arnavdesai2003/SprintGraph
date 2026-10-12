import re
import math
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from pydantic import ValidationError
from app.agents.schemas import PREvidence, SprintEvidence
from datetime import datetime, timedelta, timezone
import httpx
from app.config import settings

class ProviderError(Exception):
    def __init__(self, message, *, retryable=True, retry_after=None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def retry_after_seconds(headers):
    """Return safe bounded provider delay without retaining headers or response bodies."""
    delays = []
    value = headers.get('retry-after')
    if value:
        try:
            delays.append(float(value))
        except ValueError:
            try:
                stamp = parsedate_to_datetime(value)
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                delays.append((stamp - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    if headers.get('x-ratelimit-remaining') == '0':
        try:
            delays.append(float(headers['x-ratelimit-reset']) - datetime.now(timezone.utc).timestamp())
        except (ValueError, KeyError):
            pass
    valid = [min(86400, math.ceil(value)) for value in delays if math.isfinite(value) and value >= 0]
    return max(valid) if valid else None


def demo_issues():
    today = datetime.now(timezone.utc).date()
    return [
        {'key': 'SG-101', 'summary': 'Ship webhook ingestion', 'status': 'Done', 'priority': 'High', 'severity': 2, 'due_date': str(today), 'dependencies': [], 'sprint': True, 'updated': str(today)},
        {'key': 'SG-102', 'summary': 'Validate provider retries', 'status': 'Blocked', 'priority': 'Highest', 'severity': 4, 'due_date': str(today - timedelta(days=2)), 'dependencies': ['SG-103'], 'sprint': True, 'updated': str(today - timedelta(days=9))},
        {'key': 'SG-103', 'summary': 'Configure integration credentials', 'status': 'In Progress', 'priority': 'High', 'severity': 3, 'due_date': str(today + timedelta(days=1)), 'dependencies': [], 'sprint': True, 'updated': str(today - timedelta(days=8))},
        {'key': 'SG-104', 'summary': 'Improve dashboard accessibility', 'status': 'To Do', 'priority': 'Medium', 'severity': 1, 'due_date': None, 'dependencies': [], 'sprint': True, 'updated': str(today)},
    ]

class Clients:
    def __init__(self, *, transport=None):
        self.config = settings()
        self.transport = transport

    async def request(self, url, **kwargs):
        try:
            async with httpx.AsyncClient(timeout=25, transport=self.transport, follow_redirects=False) as client:
                response = await client.get(url, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            headers = exc.response.headers
            limited = status == 429 or (status == 403 and (
                headers.get('x-ratelimit-remaining') == '0' or 'retry-after' in headers))
            delay = retry_after_seconds(headers) if limited or status >= 500 else None
            raise ProviderError(f'Provider request failed ({status}); check configuration or retry later',
                                retryable=limited or status >= 500, retry_after=delay) from None
        except httpx.HTTPError:
            raise ProviderError('Provider request failed (transport); retry later') from None
        except ValueError:
            raise ProviderError('Provider returned invalid JSON', retryable=False) from None

    async def github_pages(self, base, resource, headers):
        items = []
        for page in range(1, 32):
            batch = await self.request(f'{base}/{resource}', headers=headers,
                                       params={'per_page': 100, 'page': page})
            if not isinstance(batch, list) or len(batch) > 100:
                raise ProviderError('Malformed GitHub pagination', retryable=False)
            items.extend(batch)
            if len(items) > 3000:
                raise ProviderError('PR exceeds supported pagination limit', retryable=False)
            if len(batch) < 100:
                return items
        raise ProviderError('PR exceeds supported pagination limit', retryable=False)

    async def pull_request(self, repository, number):
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', repository)
                or repository.split('/')[-1] in {'.', '..'} or type(number) is not int or number < 1):
            raise ProviderError('Invalid repository or PR number', retryable=False)
        if self.config.mode == 'demo':
            return {'number': number, 'repository': repository, 'title': 'Add signed webhook ingestion SG-101',
                    'body': 'Implements SG-101. Adds delivery deduplication and retries.',
                    'files': [{'filename': 'app/webhooks.py', 'additions': 120, 'deletions': 12}, {'filename': 'tests/test_webhooks.py', 'additions': 80, 'deletions': 0}],
                    'commits': [{'sha': 'demo-sha-001', 'message': 'Validate HMAC signatures'}], 'url': f'https://github.com/{repository}/pull/{number}'}
        if not self.config.github_token:
            raise ProviderError('GitHub token is not configured', retryable=False)
        base = f'https://api.github.com/repos/{repository}/pulls/{number}'
        headers = {'Authorization': f'Bearer {self.config.github_token}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
        try:
            pr = await self.request(base, headers=headers)
            # GitHub caps the PR commit listing at 250; do not report partial evidence.
            if type(pr['commits']) is not int or not 0 <= pr['commits'] <= 250:
                raise ProviderError('PR exceeds supported commit limit (250)', retryable=False)
            if type(pr['changed_files']) is not int or not 0 <= pr['changed_files'] <= 3000:
                raise ProviderError('PR exceeds supported file limit (3000)', retryable=False)
            if pr['number'] != number:
                raise ProviderError('GitHub PR identity mismatch', retryable=False)
            files = await self.github_pages(base, 'files', headers)
            commits = await self.github_pages(base, 'commits', headers)
            if len(files) != pr['changed_files'] or len(commits) != pr['commits']:
                raise ProviderError('Incomplete GitHub PR evidence; retry retrieval')
            result = {'number': number, 'repository': repository, 'title': pr['title'], 'body': pr.get('body') or '',
                      'url': pr['html_url'],
                      'files': [{'filename': f['filename'], 'additions': f['additions'], 'deletions': f['deletions']} for f in files],
                      'commits': [{'sha': c['sha'], 'message': c['commit']['message']} for c in commits]}
            evidence = PREvidence.model_validate(result).model_dump(mode='json', exclude={'linked_issues'})
            if evidence['url'] != f'https://github.com/{repository}/pull/{number}':
                raise ProviderError('GitHub PR URL mismatch', retryable=False)
            return evidence
        except (KeyError, TypeError, ValueError, ValidationError):
            raise ProviderError('Malformed GitHub response', retryable=False) from None

    def jira_base(self):
        c = self.config
        parsed = urlsplit(c.jira_url)
        host = parsed.hostname or ''
        if (not all([c.jira_url, c.jira_email, c.jira_token]) or parsed.scheme != 'https'
                or not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.atlassian\.net', host)
                or parsed.username or parsed.password or parsed.port not in {None, 443}
                or parsed.path not in {'', '/'} or parsed.query or parsed.fragment):
            raise ProviderError('Configure a Jira Cloud HTTPS site URL and credentials', retryable=False)
        return c.jira_url.rstrip('/')

    async def active_sprint(self, base, project, auth):
        active, offset = [], 0
        for _ in range(100):
            data = await self.request(f'{base}/rest/agile/1.0/board/{project.jira_board_id}/sprint',
                                      auth=auth, params={'state': 'active', 'startAt': offset, 'maxResults': 100})
            batch = data['values']
            if not isinstance(batch, list) or len(batch) > 100:
                raise ProviderError('Malformed Jira sprint pagination', retryable=False)
            active.extend(batch)
            if data.get('isLast') is True:
                break
            if not batch:
                if data.get('isLast') is False:
                    raise ProviderError('Jira sprint pagination made no progress', retryable=False)
                break
            offset += len(batch)
            if 'isLast' not in data and len(batch) < data.get('maxResults', 100):
                break
        else:
            raise ProviderError('Jira sprint pagination limit exceeded', retryable=False)
        selected = [s for s in active if self.config.jira_sprint_id is None or s['id'] == self.config.jira_sprint_id]
        if len(selected) != 1:
            raise ProviderError('Select one active sprint using JIRA_SPRINT_ID', retryable=False)
        sprint = selected[0]
        if type(sprint['id']) is not int or sprint['id'] < 1:
            raise ProviderError('Invalid Jira sprint identity', retryable=False)
        return sprint

    async def jira_issues(self, base, sprint_id, auth):
        enhanced = self.config.jira_issue_api == 'enhanced'
        endpoint = 'software' if enhanced else 'agile'
        issues, seen, offset, token = [], set(), 0, None
        for _ in range(200):
            params = {'maxResults': 100}
            if enhanced:
                if token:
                    params['nextPageToken'] = token
            else:
                params['startAt'] = offset
            data = await self.request(f'{base}/rest/{endpoint}/1.0/sprint/{sprint_id}/issue', auth=auth, params=params)
            batch = data['issues']
            if not isinstance(batch, list) or len(batch) > 100:
                raise ProviderError('Malformed Jira issue pagination', retryable=False)
            issues.extend(batch)
            if len(issues) > 10000:
                raise ProviderError('Sprint exceeds supported issue limit', retryable=False)
            if enhanced:
                if data.get('isLast') is True:
                    return issues
                next_token = data.get('nextPageToken')
                if not isinstance(next_token, str) or not next_token or next_token in seen:
                    raise ProviderError('Jira continuation token is missing or repeated', retryable=False)
                seen.add(next_token)
                token = next_token
            else:
                total = data['total']
                if type(total) is not int or total < 0 or data.get('startAt', offset) != offset:
                    raise ProviderError('Malformed Jira issue pagination', retryable=False)
                offset += len(batch)
                if offset >= total:
                    return issues
                if not batch:
                    raise ProviderError('Jira issue pagination made no progress', retryable=False)
        raise ProviderError('Jira issue pagination limit exceeded', retryable=False)

    async def sprint(self, project):
        if (type(project.jira_board_id) is not int or project.jira_board_id < 1
                or not re.fullmatch(r'[A-Z][A-Z0-9_]*', project.jira_key)):
            raise ProviderError('Invalid Jira project or board', retryable=False)
        if self.config.mode == 'demo':
            return {'id': 'demo-sprint-12', 'name': 'Sprint 12 · Reliability', 'issues': demo_issues()}
        c = self.config
        try:
            base = self.jira_base()
            auth = (c.jira_email, c.jira_token)
            sprint = await self.active_sprint(base, project, auth)
            raw = await self.jira_issues(base, sprint['id'], auth)
            issues = []
            for issue in raw:
                f = issue['fields']
                if not issue['key'].startswith(project.jira_key + '-'):
                    continue
                severity = f.get(c.jira_severity_field) if c.jira_severity_field else None
                if isinstance(severity, dict):
                    severity = severity.get('value')
                issues.append({'key': issue['key'], 'summary': f['summary'],
                               'status': c.jira_status_map.get(f['status']['name'], f['status']['name']),
                               'priority': (f.get('priority') or {}).get('name', 'Medium'),
                               'severity': c.jira_severity_map.get(str(severity), 0),
                               'due_date': f.get('duedate'), 'updated': f['updated'][:10], 'sprint': True,
                               'dependencies': sorted({link['inwardIssue']['key'] for link in f.get('issuelinks', [])
                                   if 'inwardIssue' in link and 'block' in link['type'].get('inward', '').lower()})})
            validated = SprintEvidence.model_validate({'id': str(sprint['id']), 'name': sprint['name'],
                             'issues': issues, 'reference_date': datetime.now(timezone.utc).date()})
            return validated.model_dump(mode='json', exclude={'reference_date'})
        except (KeyError, TypeError, ValueError, ValidationError):
            raise ProviderError('Malformed Jira response or configuration', retryable=False) from None
