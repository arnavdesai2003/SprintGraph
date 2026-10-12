"""Exercise live adapters over mocked HTTP; no external credentials or requests."""
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from app.config import Settings
from app.integrations.clients import Clients, ProviderError, retry_after_seconds


def jira_issue(key='SG-1', **fields):
    return {'key': key, 'fields': {'summary': 'Provider fixture', 'status': {'name': 'Doing'},
            'priority': None, 'updated': '2026-10-11T10:00:00.000+0000', 'duedate': None,
            'issuelinks': [], **fields}}


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.config = Settings(_env_file=None, jwt_secret='test-only-' * 8, mode='live',
                               github_token='test-github', jira_url='https://test-team.atlassian.net',
                               jira_email='test@example.invalid', jira_token='test-jira', jira_sprint_id=None,
                               jira_issue_api='enhanced', jira_status_map={}, jira_severity_field='',
                               jira_severity_map={})
        self.project = SimpleNamespace(jira_board_id=1, jira_key='SG')
        self.requests = []

    def client(self, handler):
        def wrapped(request):
            self.requests.append(request)
            self.assertEqual(request.method, 'GET')
            return handler(request)
        with patch('app.integrations.clients.settings', return_value=self.config):
            return Clients(transport=httpx.MockTransport(wrapped))

    def run_sprint(self, handler):
        return asyncio.run(self.client(handler).sprint(self.project))

    def github_handler(self, request):
        self.assertEqual(request.headers['authorization'], 'Bearer test-github')
        self.assertEqual(request.url.host, 'api.github.com')
        base = '/repos/sprintgraph/demo/pulls/42'
        if request.url.path == base:
            return httpx.Response(200, json={'number': 42, 'title': 'PR fixture', 'body': None,
                 'html_url': 'https://github.com/sprintgraph/demo/pull/42', 'changed_files': 101, 'commits': 1})
        if request.url.path.endswith('/files'):
            page = int(request.url.params['page'])
            files = [{'filename': f'file-{page}-{i}', 'additions': 1, 'deletions': 0}
                     for i in range(100 if page == 1 else 1)]
            return httpx.Response(200, json=files)
        return httpx.Response(200, json=[{'sha': 'abc', 'commit': {'message': 'Fixture commit'}}])

    def test_github_collects_all_pages_and_metadata(self):
        result = asyncio.run(self.client(self.github_handler).pull_request('sprintgraph/demo', 42))
        self.assertEqual(len(result['files']), 101)
        self.assertEqual(result['commits'][0]['sha'], 'abc')
        self.assertEqual(result['body'], '')
        self.assertEqual(len(self.requests), 4)

    def test_github_incomplete_file_list_fails(self):
        def handler(request):
            if request.url.path.endswith('/files'):
                return httpx.Response(200, json=[])
            return self.github_handler(request)
        with self.assertRaisesRegex(ProviderError, 'Incomplete'):
            asyncio.run(self.client(handler).pull_request('sprintgraph/demo', 42))

    def test_github_commit_cap_fails_before_collection(self):
        def handler(request):
            response = self.github_handler(request)
            data = response.json()
            data['commits'] = 251
            return httpx.Response(200, json=data)
        with self.assertRaisesRegex(ProviderError, 'commit limit') as caught:
            asyncio.run(self.client(handler).pull_request('sprintgraph/demo', 42))
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(len(self.requests), 1)

    def test_github_wrong_url_fails(self):
        def handler(request):
            response = self.github_handler(request)
            data = response.json()
            if isinstance(data, dict):
                data['html_url'] = 'https://github.com/other/repo/pull/42'
            return httpx.Response(200, json=data)
        with self.assertRaisesRegex(ProviderError, 'URL mismatch'):
            asyncio.run(self.client(handler).pull_request('sprintgraph/demo', 42))

    def test_github_wrong_shape_is_safe(self):
        with self.assertRaisesRegex(ProviderError, 'Malformed') as caught:
            asyncio.run(self.client(lambda request: httpx.Response(200, json={'private': 'body'}))
                        .pull_request('sprintgraph/demo', 42))
        self.assertNotIn('private', str(caught.exception))

    def test_boolean_pr_number_is_rejected_before_http(self):
        with self.assertRaises(ProviderError):
            asyncio.run(self.client(self.github_handler).pull_request('sprintgraph/demo', True))
        self.assertEqual(self.requests, [])

    def sprint_page(self, request):
        self.assertTrue(request.headers['authorization'].startswith('Basic '))
        return httpx.Response(200, json={'values': [{'id': 12, 'name': 'Live fixture'}], 'isLast': True})

    def test_jira_token_pagination_mapping_and_dependency_direction(self):
        self.config.jira_status_map = {'Doing': 'In Progress'}
        self.config.jira_severity_field = 'customfield_10001'
        self.config.jira_severity_map = {'Critical': 4}
        links = [{'inwardIssue': {'key': 'SG-2'}, 'type': {'inward': 'is blocked by'}},
                 {'outwardIssue': {'key': 'SG-3'}, 'type': {'outward': 'blocks'}},
                 {'inwardIssue': {'key': 'SG-4'}, 'type': {'inward': 'relates to'}}]
        def handler(request):
            if '/board/' in request.url.path:
                return self.sprint_page(request)
            self.assertEqual(request.url.path, '/rest/software/1.0/sprint/12/issue')
            if 'nextPageToken' not in request.url.params:
                return httpx.Response(200, json={'issues': [jira_issue(issuelinks=links,
                                  customfield_10001={'value': 'Critical'})], 'isLast': False, 'nextPageToken': 'page-two'})
            self.assertEqual(request.url.params['nextPageToken'], 'page-two')
            return httpx.Response(200, json={'issues': [jira_issue('SG-2'), jira_issue('OTHER-1')], 'isLast': True})
        result = self.run_sprint(handler)
        self.assertEqual(len(result['issues']), 2)
        self.assertEqual(result['issues'][0]['dependencies'], ['SG-2'])
        self.assertEqual(result['issues'][0]['status'], 'In Progress')
        self.assertEqual(result['issues'][0]['severity'], 4)
        self.assertEqual(result['issues'][0]['priority'], 'Medium')

    def test_jira_legacy_advances_by_actual_page_size(self):
        self.config.jira_issue_api = 'legacy'
        def handler(request):
            if '/board/' in request.url.path:
                return self.sprint_page(request)
            offset = int(request.url.params['startAt'])
            self.assertEqual(request.url.path, '/rest/agile/1.0/sprint/12/issue')
            return httpx.Response(200, json={'startAt': offset, 'maxResults': 1, 'total': 2,
                                           'issues': [jira_issue(f'SG-{offset + 1}')]})
        self.assertEqual(len(self.run_sprint(handler)['issues']), 2)
        self.assertEqual([r.url.params['startAt'] for r in self.requests[1:]], ['0', '1'])

    def test_jira_repeated_tokens_fail(self):
        def handler(request):
            if '/board/' in request.url.path:
                return self.sprint_page(request)
            return httpx.Response(200, json={'issues': [jira_issue()], 'isLast': False, 'nextPageToken': 'repeat'})
        with self.assertRaisesRegex(ProviderError, 'repeated'):
            self.run_sprint(handler)

    def test_jira_missing_token_does_not_silently_truncate(self):
        def handler(request):
            return self.sprint_page(request) if '/board/' in request.url.path else httpx.Response(200, json={'issues': []})
        with self.assertRaisesRegex(ProviderError, 'missing'):
            self.run_sprint(handler)

    def test_jira_duplicate_issues_fail_validation(self):
        def handler(request):
            return self.sprint_page(request) if '/board/' in request.url.path else httpx.Response(200,
                json={'issues': [jira_issue(), jira_issue()], 'isLast': True})
        with self.assertRaisesRegex(ProviderError, 'Malformed'):
            self.run_sprint(handler)

    def test_parallel_sprints_require_explicit_selection(self):
        with self.assertRaisesRegex(ProviderError, 'JIRA_SPRINT_ID'):
            self.run_sprint(lambda request: httpx.Response(200, json={'values': [
                {'id': 12, 'name': 'One'}, {'id': 13, 'name': 'Two'}], 'isLast': True}))
        self.assertEqual(len(self.requests), 1)

    def test_explicit_sprint_can_be_on_second_board_page(self):
        self.config.jira_sprint_id = 13
        def handler(request):
            if '/board/' in request.url.path:
                offset = int(request.url.params['startAt'])
                return httpx.Response(200, json={'values': [{'id': 12 + offset, 'name': 'Selected'}],
                                                'isLast': offset == 1})
            self.assertIn('/sprint/13/', request.url.path)
            return httpx.Response(200, json={'issues': [], 'isLast': True})
        self.assertEqual(self.run_sprint(handler)['id'], '13')

    def test_unsafe_jira_urls_fail_before_http(self):
        for url in ['http://test-team.atlassian.net', 'https://localhost',
                    'https://test-team.atlassian.net.evil.invalid', 'https://user:password@test-team.atlassian.net',
                    'https://test-team.atlassian.net?secret=test', 'https://test-team.atlassian.net/path']:
            with self.subTest(url=url):
                self.config.jira_url = url
                with self.assertRaises(ProviderError):
                    self.run_sprint(self.sprint_page)
        self.assertEqual(self.requests, [])

    def test_missing_credentials_fail_before_http(self):
        self.config.github_token = ''
        with self.assertRaises(ProviderError):
            asyncio.run(self.client(self.github_handler).pull_request('sprintgraph/demo', 42))
        self.config.jira_token = ''
        with self.assertRaises(ProviderError):
            self.run_sprint(self.sprint_page)
        self.assertEqual(self.requests, [])

    def test_http_failures_have_safe_retry_classification(self):
        for status, headers, retryable in [(401, {}, False), (404, {}, False), (403, {}, False),
                (429, {'Retry-After': '60'}, True), (403, {'X-RateLimit-Remaining': '0'}, True),
                (503, {'Retry-After': '30'}, True)]:
            with self.subTest(status=status):
                client = self.client(lambda request: httpx.Response(status, headers=headers, text='private-body'))
                with self.assertRaises(ProviderError) as caught:
                    asyncio.run(client.request('https://api.github.com/test'))
                self.assertEqual(caught.exception.retryable, retryable)
                self.assertNotIn('private-body', str(caught.exception))
                if 'Retry-After' in headers:
                    self.assertEqual(caught.exception.retry_after, int(headers['Retry-After']))

    def test_redirect_is_not_followed(self):
        client = self.client(lambda request: httpx.Response(302, headers={'Location': 'https://evil.invalid'}))
        with self.assertRaises(ProviderError):
            asyncio.run(client.request('https://api.github.com/test', headers={'Authorization': 'Bearer test'}))
        self.assertEqual(len(self.requests), 1)

    def test_invalid_json_is_safe_and_terminal(self):
        client = self.client(lambda request: httpx.Response(200, text='private-invalid-json'))
        with self.assertRaises(ProviderError) as caught:
            asyncio.run(client.request('https://api.github.com/test'))
        self.assertFalse(caught.exception.retryable)
        self.assertNotIn('private', str(caught.exception))

    def test_retry_headers_date_reset_and_bounds(self):
        stamp = datetime.now(timezone.utc) + timedelta(seconds=120)
        self.assertTrue(118 <= retry_after_seconds({'retry-after': format_datetime(stamp)}) <= 121)
        self.assertTrue(119 <= retry_after_seconds({'x-ratelimit-remaining': '0',
                                 'x-ratelimit-reset': str(stamp.timestamp())}) <= 121)
        self.assertEqual(retry_after_seconds({'retry-after': '99999999'}), 86400)
        for value in ['nan', 'inf', '-1', 'invalid']:
            self.assertIsNone(retry_after_seconds({'retry-after': value}))


if __name__ == '__main__':
    unittest.main()
