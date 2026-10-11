import re
from datetime import datetime, timedelta, timezone
import httpx
from app.config import settings

class ProviderError(Exception):
    pass

def demo_issues():
    today = datetime.now(timezone.utc).date()
    return [
        {'key': 'SG-101', 'summary': 'Ship webhook ingestion', 'status': 'Done', 'priority': 'High', 'severity': 2, 'due_date': str(today), 'dependencies': [], 'sprint': True, 'updated': str(today)},
        {'key': 'SG-102', 'summary': 'Validate provider retries', 'status': 'Blocked', 'priority': 'Highest', 'severity': 4, 'due_date': str(today - timedelta(days=2)), 'dependencies': ['SG-103'], 'sprint': True, 'updated': str(today - timedelta(days=9))},
        {'key': 'SG-103', 'summary': 'Configure integration credentials', 'status': 'In Progress', 'priority': 'High', 'severity': 3, 'due_date': str(today + timedelta(days=1)), 'dependencies': [], 'sprint': True, 'updated': str(today - timedelta(days=8))},
        {'key': 'SG-104', 'summary': 'Improve dashboard accessibility', 'status': 'To Do', 'priority': 'Medium', 'severity': 1, 'due_date': None, 'dependencies': [], 'sprint': True, 'updated': str(today)},
    ]

class Clients:
    def __init__(self):
        self.config = settings()

    async def request(self, url, **kwargs):
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.get(url, **kwargs)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Never persist response bodies or credentials.
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else 'transport'
            raise ProviderError(f'Provider request failed ({status}); retry later') from None

    async def pull_request(self, repository, number):
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', repository)
                or repository.split('/')[-1] in {'.', '..'} or number < 1):
            raise ProviderError('Invalid repository or PR number')
        if self.config.mode == 'demo':
            return {'number': number, 'repository': repository, 'title': 'Add signed webhook ingestion SG-101',
                    'body': 'Implements SG-101. Adds delivery deduplication and retries.',
                    'files': [{'filename': 'app/webhooks.py', 'additions': 120, 'deletions': 12}, {'filename': 'tests/test_webhooks.py', 'additions': 80, 'deletions': 0}],
                    'commits': [{'sha': 'demo-sha-001', 'message': 'Validate HMAC signatures'}], 'url': f'https://github.com/{repository}/pull/{number}'}
        if not self.config.github_token:
            raise ProviderError('GitHub token is not configured')
        base = f'https://api.github.com/repos/{repository}/pulls/{number}'
        headers = {'Authorization': f'Bearer {self.config.github_token}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
        pr = await self.request(base, headers=headers)
        files, commits = [], []
        for resource, target in [('files', files), ('commits', commits)]:
            for page in range(1, 31):
                batch = await self.request(f'{base}/{resource}', headers=headers, params={'per_page': 100, 'page': page})
                target.extend(batch)
                if len(batch) < 100:
                    break
            else:
                raise ProviderError('PR exceeds supported pagination limit')
        return {'number': number, 'repository': repository, 'title': pr['title'], 'body': pr.get('body') or '',
                'url': pr['html_url'], 'files': [{'filename': f['filename'], 'additions': f['additions'], 'deletions': f['deletions']} for f in files],
                'commits': [{'sha': c['sha'], 'message': c['commit']['message']} for c in commits]}

    async def sprint(self, project):
        if self.config.mode == 'demo':
            return {'id': 'demo-sprint-12', 'name': 'Sprint 12 · Reliability', 'issues': demo_issues()}
        c = self.config
        if not all([c.jira_url, c.jira_email, c.jira_token]) or not c.jira_url.startswith('https://'):
            raise ProviderError('Jira HTTPS URL and credentials are required')
        auth = (c.jira_email, c.jira_token)
        base = c.jira_url.rstrip('/')
        sprints = await self.request(f'{base}/rest/agile/1.0/board/{project.jira_board_id}/sprint', auth=auth, params={'state': 'active'})
        if not sprints.get('values'):
            raise ProviderError('No active sprint found')
        sprint = sprints['values'][0]
        issues = []
        for offset in range(0, 10000, 100):
            data = await self.request(f'{base}/rest/agile/1.0/sprint/{sprint["id"]}/issue', auth=auth, params={'startAt': offset, 'maxResults': 100})
            for issue in data['issues']:
                f = issue['fields']
                if not issue['key'].startswith(project.jira_key + '-'):
                    continue
                issues.append({'key': issue['key'], 'summary': f['summary'], 'status': f['status']['name'],
                               'priority': (f.get('priority') or {}).get('name', 'Medium'), 'severity': 0,
                               'due_date': f.get('duedate'), 'updated': f['updated'][:10], 'sprint': True,
                               'dependencies': [link['inwardIssue']['key'] for link in f.get('issuelinks', []) if 'inwardIssue' in link and 'block' in link['type'].get('inward', '').lower()]})
            if offset + len(data['issues']) >= data.get('total', 0):
                break
        else:
            raise ProviderError('Sprint exceeds supported pagination limit')
        return {'id': str(sprint['id']), 'name': sprint['name'], 'issues': issues}
